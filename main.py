from wxasync import WxAsyncApp
from asyncio.events import get_event_loop
import time
import wx
import aiohttp
from urllib.parse import urlencode
from utils import WinRegistry
from views.login_dialog import LoginDialog, AsyncShowDialog, Dialog2FA
from asyncio.locks import Event, Semaphore
import binascii
import traceback
from views.pickkey import KeyPickerDialog
import os
from Crypto.Cipher import AES
import struct
from binascii import unhexlify

APIURL = 'http://idonly.com:8080/api'

class ClientApiError(Exception):
    pass

class LoginRequired(Exception):
    pass

class Require2FA(Exception):
    pass


class ApiSession():
    def __init__(self):
        pass
            
    async def get(self, method, params={}, session_cookie=None):
        url = APIURL + method
        if params:
            url += "?" + urlencode(params)
        cookies = None if session_cookie is None else {"Session" : session_cookie}
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url) as resp:
                print ("get", url, session_cookie)
                #if session:
                #    #self.session.cookie_jar.clear()
                #    #self.session.cookie_jar.update_cookies({"Session" : cookie}.items())
                #    #print ("----", self.session.cookie_jar["Session"])
                result = await resp.json()
                print (result)
                #self.cookies = resp.cookies
                if 'error' in result:
                    if result["error"] == "Login required":
                        raise LoginRequired(result["error"])
                    elif result["error"] == "Please submit a 2FA token and resubmit this request":
                        raise Require2FA(result["error"])
                    else:
                        traceback.print_exc()
                        raise ClientApiError(result["error"])
                return result["result"], resp.cookies["Session"].value

class CachedApiSession():
    def __init__(self, session_cache=WinRegistry):
        self.api_session = ApiSession()
        self.session_cache = session_cache
            
    async def get(self, method, params={}):
        session_time = self.session_cache.get("session_time")
        if session_time is None or int(session_time) < time.time() - (20*60-30): # 20min-30sec as sessions expire after 20min
            localsecret = self.session_cache.get("localsecret")
            if localsecret is None:
                result, session_cookie = await self.api_session.get("/user/device_login")
                self.session_cache.set("localsecret", result["localsecret"])
            else:
                result, session_cookie = await self.api_session.get("/user/device_login", {"localsecret" : localsecret})
            print (session_cookie)
            self.session_cache.set("session", session_cookie)
            self.session_cache.set("session_time", str(int(time.time())))
        else:
            session_cookie = self.session_cache.get("session")
            localsecret = self.session_cache.get("localsecret")
        result, _session_cookie = await self.api_session.get(method, params, session_cookie)
        return result 


class ApiSessionWithDialogs():
    def __init__(self):
        self.session = CachedApiSession()
        self.login_semaphore = Semaphore()
        self.logged_in = False

    '''async def device_login(self):
        if not self.device_logged_in:
            localsecret = self.session_cache.get("localsecret")
            if localsecret is None:
                localsecret = await self.get("/user/device_login")["localsecret"]
                self.session_cache.set("localsecret", localsecret)
            else:
                await self.session.get("/user/device_login", {"localsecret" : localsecret})
            self.device_logged_in = True'''

    async def get_with_login(self, method, params={}):
        try:
            result = await self.session.get(method, params)
        except LoginRequired:       
            await self.login_semaphore.acquire()
            if not self.logged_in:
                await self.DoLogin()
            self.login_semaphore.release()
            return await self.session.get(method, params)
        return result
    
    async def get(self, method, params={}):
        try:
            result = await self.get_with_login(method, params)
        except Require2FA:
            async def On2FA(otp):
                result = await self.session.get("/user/otp", {"otp": otp})
                print (result)
            dlg = Dialog2FA(Handle2FACoroutine=On2FA)
            await AsyncShowDialog(dlg)
            #otp = dlg.GetValue()
            result = await self.get_with_login(method, params)
        return result
        
    async def DoLogin(self):
        login_completed = Event()

        async def HandleLogin(username, password):
            result = await self.session.get("/user/login", {"email": username, "password": password})
            login_completed.set()
    
        async def HandleCreateAccountStep1(username):
            await self.get("/user/register", {"email": username})
    
        async def HandleCreateAccountStep2(confirmation_code, username, password, otp_secret):
            await self.get("/user/register_confirm" , {"confirmation_code": confirmation_code, "password": password, "otp_secret": otp_secret})
            await self.session.get("/user/login", {"email": username, "password": password})
            login_completed.set()
    
        login_dialog = LoginDialog(None, HandleLogin=HandleLogin,  HandleCreateAccountStep1=HandleCreateAccountStep1,  HandleCreateAccountStep2=HandleCreateAccountStep2)
        login_dialog.Show()
        await login_completed.wait()
        login_dialog.Hide()


DATALEN = 1024*1024    
NONCE_SIZE = 16
AESKEYSIZE = 32
TAG_SIZE = 16


async def encrypt(filename, filename_out=None, randfunc=os.urandom):
    api_session = ApiSessionWithDialogs()
    keys = await api_session.get(f"/key/list")
    algorithms = await api_session.get(f"/key/list_algorithms")
    async def HandleNewKey(label, algorithm, security):
        result = await api_session.get(f"/key/create", {"label" : label, "algorithm" : algorithm, "security" : security})
        return result
    dlg = KeyPickerDialog(keys, algorithms, HandleNewKey=HandleNewKey)
    result = await AsyncShowDialog(dlg)
    if filename_out is None:
        filename_out = filename + ".enc"
    if result == wx.ID_OK:
        key = dlg.GetValue()
        secret = randfunc(AESKEYSIZE)
        secret_encrypted = await api_session.get("/key/encrypt" , {"message": binascii.hexlify(secret), "key_id": key["identifier"]})
        secret_encrypted_bin = binascii.unhexlify(secret_encrypted)
        with open(filename_out, "wb") as fout:
            fout.write(struct.pack("Q", len(secret_encrypted_bin)))
            fout.write(secret_encrypted_bin)
            fout.write(struct.pack("Q", int(key["identifier"])))
            with open(filename, "rb") as fin:
                data = fin.read(DATALEN)
                while data:
                    nonce = randfunc(NONCE_SIZE)
                    cipher = AES.new(secret, AES.MODE_GCM, nonce=nonce)
                    ciphertext, tag = cipher.encrypt_and_digest(data)
                    fout.write(nonce + tag + ciphertext)
                    data = fin.read(DATALEN)



async def decrypt(filename):
    api_session = ApiSessionWithDialogs()
    keys = await api_session.get(f"/key/list")
    assert filename[-4:] == ".enc"
    filename_out = filename[:-4] + ".plain"

    with open(filename_out, "wb") as fout:
        with open(filename, "rb") as fin:
            secret_len, = struct.unpack("Q", fin.read(8))
            secret_encrypted_bin = fin.read(secret_len)
            key_id_bin = fin.read(8)
            key_id, = struct.unpack("Q", key_id_bin)
            key_id = str(key_id)
            if not any(k["identifier"] == key_id for k in keys):
                raise Exception("Key not found")
            secret_hex = await api_session.get("/key/decrypt" , {"message": binascii.hexlify(secret_encrypted_bin), "key_id":  key_id})
            secret = unhexlify(secret_hex)
            
            data = fin.read(DATALEN + NONCE_SIZE + TAG_SIZE)
            while data:
                nonce = data[:NONCE_SIZE]
                tag = data[NONCE_SIZE:NONCE_SIZE+TAG_SIZE]
                encrypted = data[NONCE_SIZE+TAG_SIZE:]
                cipher = AES.new(secret, AES.MODE_GCM, nonce=nonce)
                plain = cipher.decrypt_and_verify(encrypted, tag)
                fout.write(plain)
                data = fin.read(DATALEN + NONCE_SIZE + TAG_SIZE)

'''
async def main():
    loop = get_event_loop()
    #await device_login(api_session)
    app = WxAsyncApp()
    task = loop.create_task(app.MainLoop())
    
    await encrypt(r"c:\tmp\02-04_news.txt")
    await decrypt(r"c:\tmp\02-04_news.txt.enc")
    
    task.cancel()
    #res = await api_session.get(f"/user/login", {"email": "sirk390@gmail.com", "password": "a"})
'''
 

async def async_gui(coroutine):
    loop = get_event_loop()
    app = WxAsyncApp()
    task = loop.create_task(app.MainLoop())
    try:
        await coroutine
    except Exception as e:
        dlg = wx.MessageDialog(None, str(e), "Error")
        dlg.ShowModal()
    finally:
        task.cancel()        
    
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--encrypt", action="store_true", help="Encrypt a file")
    parser.add_argument("--decrypt", action="store_true", help="Decrypt a file")
    parser.add_argument("filename", type=str, help="Filename")
    args = parser.parse_args()
    loop = get_event_loop()
    if args.encrypt:
        task = async_gui(encrypt(args.filename))
    else:
        task = async_gui(decrypt(args.filename))
        
    loop.run_until_complete(task)
    