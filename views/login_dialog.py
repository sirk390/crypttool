import qrcode
import wx
from wx.adv import EVT_HYPERLINK
from wx._adv import HyperlinkCtrl
from wx._core import Colour
import pyotp
from wxasync import AsyncBind, WxAsyncApp
from asyncio.events import get_event_loop
from asyncio.locks import Event
from enum import Enum

async def AsyncShowDialog(dlg):
    closed = Event()
    def end_dialog(return_code):
        dlg.SetReturnCode(return_code)
        dlg.Hide()
        closed.set()
    async def on_button(event):
        # Same code as in wxwidgets:/src/common/dlgcmn.cpp:OnButton
        # to automatically handle OK, CANCEL, APPLY,... buttons
        id = event.GetId()
        if id == dlg.GetAffirmativeId():
            if dlg.Validate() and dlg.TransferDataFromWindow():
                end_dialog(id)
        elif id == wx.ID_APPLY:
            if dlg.Validate():
                dlg.TransferDataFromWindow()
        elif id == dlg.GetEscapeId() or (id == wx.ID_CANCEL and dlg.GetEscapeId() == wx.ID_ANY):
            end_dialog(wx.ID_CANCEL)
        else:
            event.Skip()
    async def on_close(event):
        closed.set()
        dlg.Hide()
    AsyncBind(wx.EVT_CLOSE, on_close, dlg)
    AsyncBind(wx.EVT_BUTTON, on_button, dlg)
    dlg.Show()
    await closed.wait()
    return dlg.GetReturnCode()




def Validate2FA(self):
    result = self.totp.verify(self.verify_value.GetValue())
    if not result:
        self.ShowError("Invalid Verification Code")
    else:
        self.Clear()
    return result

class CreateAccountPanelStep1(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        vbox = wx.BoxSizer(wx.VERTICAL)
        email =  wx.StaticText(self, label="Email Address:")
        self.email_value =  wx.TextCtrl(self)

        # Sizers
        vbox.Add(email)
        vbox.Add(self.email_value, 0, wx.EXPAND|wx.ALL)
        self.SetSizer(vbox)


DESCRIPTION = "A confirmation email was sent to the address '%s'. To register, please enter the confirmation code below:"

class CreateAccountPanelStep2(wx.Panel):
    def __init__(self, parent, issuer_name="Crypt Tool"):
        super().__init__(parent)
        self.issuer_name = issuer_name
        self.username = ''

        # TODO: Statictext wrapping is not so good
        self.description =  wx.StaticText(self, label="")

        confirmation_code =  wx.StaticText(self, label="Confirmation Code:")
        self.confirmation_code =  wx.TextCtrl(self)
        password =  wx.StaticText(self, label="Password")
        self.password_value =  wx.TextCtrl(self, style=wx.TE_PASSWORD)
        instructions =  wx.StaticText(self, label="Please scan this QR code using your mobile App:")
        self.qrcode = wx.StaticBitmap(self, bitmap=wx.Bitmap(100, 100))
        verif_2fa =  wx.StaticText(self, label="And enter the verification code below:")
        self.verify_value =  wx.TextCtrl(self)

        self.otp_secret = pyotp.random_base32()
        self.totp = pyotp.totp.TOTP(self.otp_secret)

        vbox = wx.BoxSizer(wx.VERTICAL)

        # Wrap StaticText as described in https://stackoverflow.com/questions/4599688/wxpython-problems-with-wrapping-statictext
        self.description.Bind(wx.EVT_SIZE, self.WrapText)


        # Sizers
        vbox.Add(self.description, 0, wx.EXPAND|wx.ALL)
        vbox.AddSpacer(10)
        vbox.Add(confirmation_code)
        vbox.Add(self.confirmation_code, 0, wx.EXPAND|wx.ALL)
        vbox.AddSpacer(10)
        vbox.Add(password)
        vbox.Add(self.password_value, 0, wx.EXPAND|wx.ALL)
        #vbox.AddStretchSpacer(4)
        vbox.AddSpacer(10)
        vbox.Add(instructions)
        vbox.AddSpacer(10)
        vbox.Add(self.qrcode, 1,  wx.ALIGN_LEFT)
        vbox.Add(verif_2fa)
        vbox.Add(self.verify_value, 0, wx.EXPAND|wx.ALL)
        self.SetSizer(vbox)
        self.prevwidth = None

    def WrapText(self, event):

        self.description.Wrap(event.GetSize()[0])

    def SetUsername(self, username):
        self.username = username
        provisioning_uri = self.totp.provisioning_uri(self.username, issuer_name=self.issuer_name)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=5,
            border=0 )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        image = wx.Image(*img.size)
        image.SetData(img.convert("RGB").tobytes())
        #image.SetAlphaData(img.convert("RGBA").tobytes()[3::4])
        self.qrcode.SetBitmap(wx.Bitmap(image))
        self.description.SetLabel(DESCRIPTION % (self.username))


class LoginPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        vbox = wx.BoxSizer(wx.VERTICAL)
        email =  wx.StaticText(self, label="Email Address:")
        self.email =  wx.TextCtrl(self)
        password =  wx.StaticText(self, label="Password")
        self.password =  wx.TextCtrl(self, style=wx.TE_PASSWORD)
        #self.login =  wx.Button(self, label="Login")
        vbox.Add(email)
        vbox.Add(self.email, 0, wx.EXPAND|wx.ALL)
        vbox.AddSpacer(10)
        vbox.Add(password)
        vbox.Add(self.password, 0, wx.EXPAND|wx.ALL)
        vbox.AddSpacer(10)
        self.SetSizer(vbox)
        self.Layout()

async def NullCoroutine(*args):
    pass


LoginState = Enum("LoginState", "Login CreateAccountStep1 CreateAccountStep2")


'''import wx.lib.inspection'''


class LoginDialog(wx.Dialog):
    def __init__(self, parent=None, title="Crypt Client", HandleLogin=NullCoroutine, HandleCreateAccountStep1=NullCoroutine, HandleCreateAccountStep2=NullCoroutine):
        super(LoginDialog, self).__init__(parent, title=title, size=(380, 450), style=wx.RESIZE_BORDER|wx.DEFAULT_DIALOG_STYLE)
        self.title =  wx.StaticText(self)
        font = self.title.GetFont()
        font.SetPointSize(16)
        self.title.SetFont(font)
        self.login_panel = LoginPanel(self)
        self.error_message =  wx.StaticText(self, label="")
        self.error_message.SetForegroundColour(Colour("Red"))
        self.create_account_panel_step1 = CreateAccountPanelStep1(self)
        self.create_account_panel_step2 = CreateAccountPanelStep2(self)
        self.link = HyperlinkCtrl(self, label="Go to Login")
        self.SetState(LoginState.Login)

        #vbox.Add(self.login, 0, wx.ALIGN_RIGHT)
        #self.create_acount_link = HyperlinkCtrl(self, label="Create new account")

        self.submit =  wx.Button(self, label="Submit")

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.title, 0, wx.TOP|wx.RIGHT|wx.LEFT, border=20 )
        vbox.AddSpacer(10)
        vbox.Add(self.create_account_panel_step1, 3, wx.EXPAND|wx.RIGHT|wx.LEFT, border=20 )
        vbox.Add(self.create_account_panel_step2, 3, wx.EXPAND|wx.RIGHT|wx.LEFT, border=20 )
        vbox.Add(self.login_panel, 3, wx.EXPAND|wx.RIGHT|wx.LEFT, border=20 )
        vbox.Add(self.error_message, 0,  wx.RIGHT|wx.LEFT, border=20 )
        vbox.AddStretchSpacer(0)
        vbox.Add(self.link, 0, wx.EXPAND|wx.RIGHT|wx.LEFT, border=20)
        vbox.Add(self.submit, 0, wx.ALIGN_RIGHT|wx.RIGHT|wx.LEFT|wx.BOTTOM, border=20)

        self.SetSizer(vbox)
        self.link.Bind(EVT_HYPERLINK, lambda event: self.OnLink())
        #self.create_account_panel_step1.login_link.Bind(EVT_HYPERLINK, lambda event: self.SetState(LoginState.Login))
        #self.create_account_panel.create_account.Bind(wx.EVT_BUTTON, self.SubmitCreateAccount)
        AsyncBind(wx.EVT_BUTTON, self.Submit, self.submit)
        #AsyncBind(wx.EVT_BUTTON, self.SubmitLogin, self.login_panel.login)
        self.HandleCreateAccountStep1 = HandleCreateAccountStep1
        self.HandleCreateAccountStep2 = HandleCreateAccountStep2
        self.HandleLogin = HandleLogin
        self.Layout()

    def OnLink(self):
        if self.state == LoginState.Login:
            self.SetState(LoginState.CreateAccountStep1)
        else:
            self.SetState(LoginState.Login)

    def SetTitle(self, title):
        self.title.SetLabel(title)

    def ShowError(self, message):
        self.error_message.SetForegroundColour(Colour("Red"))
        self.error_message.SetLabel(message)

    def ShowSuccess(self, message):
        self.error_message.SetForegroundColour(Colour(0,128,0))
        self.error_message.SetLabel(message)

    def Clear(self):
        self.error_message.SetLabel("")

    async def Submit(self, event):
        if self.state == LoginState.Login:
            await self.SubmitLogin(event)
        elif self.state == LoginState.CreateAccountStep1:
            await self.CreateAccountStep1(event)
        elif self.state == LoginState.CreateAccountStep2:
            await self.CreateAccountStep2(event)

    async def SubmitLogin(self, event):
        username = self.login_panel.email.GetValue()
        password = self.login_panel.password.GetValue()
        if not username:
            return self.ShowError("Please enter username")
        if not password:
            return self.ShowError("Please enter password")
        self.Clear()
        try:
            await self.HandleLogin(username, password)
        except Exception as e:
            self.ShowError(str(e))

    async def CreateAccountStep1(self, event):
        username = self.create_account_panel_step1.email_value.GetValue()
        try:
            await self.HandleCreateAccountStep1(username)
        except Exception as e:
            self.ShowError(str(e))
            return
        self.create_account_panel_step2.SetUsername(username)
        self.SetState(LoginState.CreateAccountStep2)

    async def CreateAccountStep2(self, event):
        password = self.create_account_panel_step2.password_value.GetValue()
        confirmation_code = self.create_account_panel_step2.confirmation_code.GetValue()
        if not password:
            return self.ShowError("Please enter password")
        if not confirmation_code:
            return self.ShowError("Please enter confirmation_code")
        verify_value = self.create_account_panel_step2.verify_value.GetValue()
        result = self.create_account_panel_step2.totp.verify(verify_value)
        otp_secret = self.create_account_panel_step2.otp_secret
        username = self.create_account_panel_step2.username
        if not result:
            return self.ShowError("Invalid 2FA Verification Value")
        else:
            self.Clear()
        try:
            await self.HandleCreateAccountStep2(confirmation_code, username, password, otp_secret)
        except Exception as e:
            self.ShowError(str(e))
            return

    def SetState(self, state):
        self.state = state
        self.Clear()
        if self.state == LoginState.Login:
            self.SetTitle("Login")
            self.login_panel.Show()
            self.create_account_panel_step1.Hide()
            self.create_account_panel_step2.Hide()
            self.link.SetLabel("Create Account")
            self.SetSize((300, 340))
        elif self.state == LoginState.CreateAccountStep1:
            self.SetTitle("Create Account")
            self.create_account_panel_step1.Show()
            self.create_account_panel_step2.Hide()
            self.login_panel.Hide()
            self.link.SetLabel("Go to Login")
            self.SetSize((300, 340))
        elif self.state == LoginState.CreateAccountStep2:
            self.SetTitle("Email Confirmation")
            self.create_account_panel_step1.Hide()
            self.create_account_panel_step2.Show()
            self.login_panel.Hide()
            self.link.SetLabel("Go to Login")
            self.SetSize((300, 600))
        self.Layout()


class Panel2FA(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        vbox = wx.BoxSizer(wx.VERTICAL)
        label_2fa =  wx.StaticText(self, label="Please enter a 2FA Token:")
        self.text_2fa =  wx.TextCtrl(self)
        #self.login =  wx.Button(self, label="Login")
        vbox.Add(label_2fa)
        vbox.Add(self.text_2fa, 0, wx.EXPAND|wx.ALL)
        vbox.AddSpacer(10)
        self.SetSizer(vbox)
        self.Layout()


class Dialog2FA(wx.Dialog):
    def __init__(self, parent=None, title="2FA Required", Handle2FACoroutine=NullCoroutine):
        super(Dialog2FA, self).__init__(parent, title=title, size=(350, 250), style=wx.RESIZE_BORDER|wx.DEFAULT_DIALOG_STYLE)
        self.Handle2FACoroutine = Handle2FACoroutine
        self.panel = Panel2FA(self)
        self.error_message =  wx.StaticText(self, label="")
        self.error_message.SetForegroundColour(Colour("Red"))

        self.submit =  wx.Button(self, label="Submit")
        AsyncBind(wx.EVT_BUTTON, self.OnSubmit, self.submit)
        #self.submit.SetId(wx.ID_OK)
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.AddSpacer(40)
        vbox.Add(self.panel, 1, wx.EXPAND|wx.RIGHT|wx.LEFT, border=20 )
        vbox.Add(self.error_message, 0,  wx.RIGHT|wx.LEFT, border=20 )
        vbox.AddStretchSpacer(1)
        vbox.Add(self.submit, 0, wx.ALIGN_RIGHT|wx.RIGHT|wx.LEFT|wx.BOTTOM, border=20)
        self.SetSizer(vbox)
        self.Layout()
        
    async def OnSubmit(self, event):
        self.error_message.SetLabel("")
        try:
            await self.Handle2FACoroutine(self.panel.text_2fa.GetValue())
            self.Close()
        except Exception as e:
            self.error_message.SetLabel(str(e))
        



if __name__ == '__main__':
    app = WxAsyncApp()
    # f = wx.Frame(None)
    login = LoginDialog(None)
    login.Show()
    #wx.lib.inspection.InspectionTool().Show()

    loop = get_event_loop()
    loop.run_until_complete(app.MainLoop())
