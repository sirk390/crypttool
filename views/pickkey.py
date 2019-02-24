import wx
from wx._core import Colour
from wxasync import AsyncBind, WxAsyncApp
from asyncio.events import get_event_loop
from views.login_dialog import AsyncShowDialog, NullCoroutine
import asyncio


class ListCtrlComboPopup(wx.ComboPopup):
    def __init__(self):
        wx.ComboPopup.__init__(self)
        self.lc = None

    def AddItem(self, label, id, algorithm, security, public_key):
        item = self.lc.InsertItem(self.lc.GetItemCount(), self.lc.GetItemCount())
        self.lc.SetItem(item, 0, label)
        self.lc.SetItem(item, 1, str(id))
        self.lc.SetItem(item, 2, algorithm)
        self.lc.SetItem(item, 3, security)
        #self.lc.SetItem(item, 4, public_key)

    def OnMotion(self, evt):
        item, flags = self.lc.HitTest(evt.GetPosition())
        if item >= 0:
            self.lc.Select(item)
            self.curitem = item

    def OnLeftDown(self, evt):
        self.value = self.curitem
        self.Dismiss()


    # The following methods are those that are overridable from the
    # ComboPopup base class.  Most of them are not required, but all
    # are shown here for demonstration purposes.

    # This is called immediately after construction finishes.  You can
    # use self.GetCombo if needed to get to the ComboCtrl instance.
    def Init(self):
        self.value = -1
        self.curitem = -1
        
    # Create the popup child control.  Return true for success.
    def Create(self, parent):
        self.lc = wx.ListCtrl(parent, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.lc.Bind(wx.EVT_MOTION, self.OnMotion)
        self.lc.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.lc.AppendColumn("Label")
        self.lc.AppendColumn("ID")
        self.lc.AppendColumn("Algorithm")
        self.lc.AppendColumn("Security")
        #self.lc.AppendColumn("Public Key")
        self.lc.SetColumnWidth(1, 140)
        self.lc.SetColumnWidth(2, 160)
        #self.lc.SetColumnWidth(4, 500)
        return True

    # Return the widget that is to be used for the popup
    def GetControl(self):
        return self.lc

    # Called just prior to displaying the popup, you can use it to
    # 'select' the current item.
    def SetStringValue(self, val):
        idx = self.lc.FindItem(-1, val)
        if idx != wx.NOT_FOUND:
            self.lc.Select(idx)

    # Return a string representation of the current item.
    def GetStringValue(self):
        if self.value >= 0:
            return self.lc.GetItemText(self.value)
        return ""

    # Called immediately after the popup is shown
    def OnPopup(self):
        wx.ComboPopup.OnPopup(self)

    # Called when popup is dismissed
    def OnDismiss(self):
        wx.ComboPopup.OnDismiss(self)

    # This is called to custom paint in the combo control itself
    # (ie. not the popup).  Default implementation draws value as
    # string.
    def PaintComboControl(self, dc, rect):
        wx.ComboPopup.PaintComboControl(self, dc, rect)

    # Receives key events from the parent ComboCtrl.  Events not
    # handled should be skipped, as usual.
    def OnComboKeyEvent(self, event):
        wx.ComboPopup.OnComboKeyEvent(self, event)

    # Implement if you need to support special action when user
    # double-clicks on the parent wxComboCtrl.
    def OnComboDoubleClick(self):
        wx.ComboPopup.OnComboDoubleClick(self)

    # Return final size of popup. Called on every popup, just prior to OnPopup.
    # minWidth = preferred minimum width for window
    # prefHeight = preferred height. Only applies if > 0,
    # maxHeight = max height for window, as limited by screen size
    #   and should only be rounded down, if necessary.
    def GetAdjustedSize(self, minWidth, prefHeight, maxHeight):
        return wx.ComboPopup.GetAdjustedSize(self, minWidth, prefHeight, maxHeight)

    # Return true if you want delay the call to Create until the popup
    # is shown for the first time. It is more efficient, but note that
    # it is often more convenient to have the control created
    # immediately.
    # Default returns false.
    def LazyCreate(self):
        return wx.ComboPopup.LazyCreate(self)


class KeySelectCombo(wx.ComboCtrl):
    def __init__(self, keys, parent=None):
        super().__init__(parent, style=wx.CB_READONLY)
        self.popupCtrl = ListCtrlComboPopup()
        self.keys = keys
        self.SetPopupControl(self.popupCtrl)
        for k in keys:
            self.popupCtrl.AddItem(k["label"], k["identifier"], k["algorithm"], str(k["security"]), k["public_key"])
    
    def GetValue(self):
        return self.keys[self.popupCtrl.value]

    def AddKey(self, k):
        self.popupCtrl.AddItem(k["label"], k["identifier"], k["algorithm"], str(k["security"]), k["public_key"])
        self.keys.append(k)

    def SelectLast(self):
        last = self.popupCtrl.lc.GetItemCount()
        self.popupCtrl.lc.Select(last)

        '''vbox = wx.BoxSizer(wx.VERTICAL)
        label_2fa =  wx.StaticText(self, label="Please enter a 2FA Token:")
        self.text_2fa =  wx.TextCtrl(self)
        vbox.Add(label_2fa)
        vbox.Add(self.text_2fa, 0, wx.EXPAND|wx.ALL)
        vbox.AddSpacer(10)
        self.SetSizer(vbox)
        self.Layout()'''


class KeyPickerDialog(wx.Dialog):
    def __init__(self, keys, algorithms, parent=None, title="Select a Key", HandleNewKey=NullCoroutine):
        super().__init__(parent, title=title, size=(550, 250), style=wx.RESIZE_BORDER|wx.DEFAULT_DIALOG_STYLE)
        self.algorithms = algorithms
        self.HandleNewKey = HandleNewKey
        self.key_label =  wx.StaticText(self, label="Key:")
        self.combo = KeySelectCombo(keys, parent=self)
        self.checkbox_default =  wx.CheckBox(self, label="Save as Default")
        
        self.error_message =  wx.StaticText(self, label="")
        self.error_message.SetForegroundColour(Colour("Red"))

        self.submit =  wx.Button(self, label="Submit")
        self.submit.SetId(wx.ID_OK)
        self.submit.SetFocus()
        self.cancel =  wx.Button(self, label="Cancel")
        self.cancel.SetId(wx.ID_CANCEL)

        self.newkey =  wx.Button(self, label="Create New")

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.AddSpacer(40)
        vbox.Add(self.key_label, 0, wx.EXPAND|wx.RIGHT|wx.LEFT, border=20 )

        hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        hbox1.Add(self.combo, 1, wx.EXPAND)
        hbox1.Add(self.newkey, 0)
        vbox.Add(hbox1, 0, wx.RIGHT|wx.LEFT|wx.EXPAND, border=20 )
        vbox.AddSpacer(20)
        vbox.Add(self.checkbox_default, 0, wx.RIGHT|wx.LEFT|wx.ALIGN_RIGHT, border=20 )
        vbox.Add(self.error_message, 0,  wx.RIGHT|wx.LEFT, border=20 )
        vbox.AddStretchSpacer(1)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        #button_sizer = wx.StdDialogButtonSizer()
        button_sizer.Add(self.cancel)
        button_sizer.Add(self.submit)
        
        vbox.Add(button_sizer, 1, wx.ALIGN_RIGHT|wx.RIGHT|wx.LEFT|wx.BOTTOM, border=20)
        self.SetSizer(vbox)
        self.Layout()
        
        AsyncBind(wx.EVT_BUTTON, self.OnNewKey, self.newkey)


    def GetValue(self):
        return self.combo.GetValue()

    async def OnNewKey(self, event):
        dlg = NewKeyDialog(algorithms=self.algorithms, HandleNewKey=self.HandleNewKey)
        result = await AsyncShowDialog(dlg)
        if result == wx.ID_OK:
            self.combo.AddKey(dlg.GetValue())
            self.combo.SelectLast()
                
    def ShowError(self, message):
        self.error_message.SetForegroundColour(Colour("Red"))
        self.error_message.SetLabel(message)

    def Clear(self):
        self.error_message.SetLabel("")


class NewKeyDialog(wx.Dialog):
    def __init__(self, parent=None, title="New Key", algorithms=[], HandleNewKey=NullCoroutine):
        super().__init__(parent, title=title, size=(550, 300), style=wx.RESIZE_BORDER|wx.DEFAULT_DIALOG_STYLE)
        self.HandleNewKey = HandleNewKey
        self.key_label_label =  wx.StaticText(self, label="Label:")
        self.key_label =  wx.TextCtrl(self)
        self.algorithm_label =  wx.StaticText(self, label="Algorithm:")
        self.algorithm =  wx.ComboBox(self, choices=algorithms, style=wx.CB_READONLY)
        self.security_label =  wx.StaticText(self, label="Security:")
        self.security =  wx.ComboBox(self, choices=[str(i) for i in range(1, 5)], style=wx.CB_READONLY)
        
        self.gauge = wx.Gauge(self)
        self.gauge.Hide()
        self.error_message =  wx.StaticText(self, label="")
        self.error_message.SetForegroundColour(Colour("Red"))

        self.submit =  wx.Button(self, label="Submit")
        self.submit.SetId(wx.ID_OK)
        self.submit.SetFocus()
        AsyncBind(wx.EVT_BUTTON, self.OnSubmit, self.submit)
        self.cancel =  wx.Button(self, label="Cancel")
        self.cancel.SetId(wx.ID_CANCEL)
        # spacers
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.AddSpacer(40)
        vbox.Add(self.key_label_label, 0, wx.EXPAND|wx.RIGHT|wx.LEFT, border=20 )
        vbox.Add(self.key_label, 0, wx.EXPAND|wx.RIGHT|wx.LEFT, border=20 )
        vbox.Add(self.algorithm_label, 0, wx.EXPAND|wx.RIGHT|wx.LEFT, border=20 )
        vbox.Add(self.algorithm, 0, wx.EXPAND|wx.RIGHT|wx.LEFT, border=20 )
        vbox.Add(self.security_label, 0, wx.EXPAND|wx.RIGHT|wx.LEFT, border=20 )
        vbox.Add(self.security, 0, wx.EXPAND|wx.RIGHT|wx.LEFT, border=20 )
        vbox.AddSpacer(20)
        vbox.Add(self.gauge, 0,  wx.EXPAND|wx.RIGHT|wx.LEFT, border=20 )
        vbox.Add(self.error_message, 0,  wx.RIGHT|wx.LEFT, border=20 )
        vbox.AddStretchSpacer(1)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(self.cancel)
        button_sizer.Add(self.submit)
        vbox.Add(button_sizer, 1, wx.ALIGN_RIGHT|wx.RIGHT|wx.LEFT|wx.BOTTOM, border=20)
        self.SetSizer(vbox)
        self.Layout()
        
    def ShowError(self, message):
        self.error_message.SetForegroundColour(Colour("Red"))
        self.error_message.SetLabel(message)
        
    def ShowSuccess(self, message):
        self.error_message.SetForegroundColour(Colour(0,128,0))
        self.error_message.SetLabel(message)

    def Clear(self):
        self.error_message.SetLabel("")
    
    async def OnSubmit(self, event):
        if self.algorithm.GetValue() is "":
            self.ShowError("Please select an algorithm")
            return False
        elif self.security.GetValue() is "":
            self.ShowError("Please select the key security level")
            return False
        self.Clear()
        self.EnableAll(False)
        label = self.key_label.GetValue()
        algorithm = self.algorithm.GetValue()
        security = self.security.GetValue()
        loop = get_event_loop()
        pulse = loop.create_task(self.pulse())
        try:
            self.result = await self.HandleNewKey(label, algorithm, security)
        except Exception as e:
            self.ShowError(str(e))
        else:
            self.ShowSuccess("Succesfully created")
            await asyncio.sleep(0.5)
            self.SetReturnCode(wx.ID_OK)
            self.Close()
        finally:
            pulse.cancel()
            self.EnableAll(True)

    def EnableAll(self, enable=False):
        self.key_label.Enable(enable)
        self.algorithm.Enable(enable)
        self.security.Enable(enable)
        self.submit.Enable(enable)
        self.cancel.Enable(enable)
        self.gauge.Show(not enable)
        self.Layout()
        
    async def pulse(self):
        while True:
            self.gauge.Pulse()
            await asyncio.sleep(0.5)

    def GetValue(self):
        return self.result

if __name__ == '__main__':
    KEYS = [{'identifier': 6496447941681610773, 'label': 'a1', 'algorithm': 'ENCRYPT_RSA_1024_OAEP', 'security': 3, 'created': 1548873887, 'public_key': '30819f300d06092a864886f70d010101050003818d0030818902818100a237207518b56ab3fb3ff48e87776092031ae98e7d1cbc5d66952a61c96bb2189859199e80fc8071476d93b12583c606a0706c1ff7fecbbaae044191d1ce86511d7be819d4c5c2f190c6c779b92232cb5453fd8fc5ddcc1a095aeab84f7a8a3a9632a04161ffed2dc419794c969159f64363f315b6a4d7042ef3ddf3965bfc1d0203010001'}, {'identifier': 6496643224503844904, 'label': 'Key2', 'algorithm': 'ENCRYPT_RSA_1024_OAEP', 'security': 3, 'created': 1548920446, 'public_key': '30819f300d06092a864886f70d010101050003818d0030818902818100e494a82937bce17f34e74fe0c4eace335d6d2e1cbf0d9601dd67e69faff6557e9090409a5b7976de51c6f445a19491281e2a609d0cc8d431f73a77ea60cf9172cd67f1b5f2215adde056d048260364eab8cced440472523127b38b4a258a0b2860539bfee9fe54cb2c6ebef39519375587445263a6428e41eb257cd0232348630203010001'}, {'identifier': 6496643148125569061, 'label': 'Key1', 'algorithm': 'ENCRYPT_RSA_1024_OAEP', 'security': 3, 'created': 1548920428, 'public_key': '30819f300d06092a864886f70d010101050003818d0030818902818100b4257abbfaec1f8a396fc761cc43b68940c7eb802a0c60ee66659ba6103daa797c46f23398695824b0579299bb4fda53d59fe05586632055646ffd19d3d340bd033075a92f5df0fad27c2d2c6b78a2fb6861213954996f1bd36162a0dd60000abbecdbcd42ecc1f1a602aa1cc81e3133b4e1211ea3fc2b38cea267c1b34705b50203010001'}, {'identifier': 6496448157537271832, 'label': 'b1', 'algorithm': 'ENCRYPT_RSA_1024_OAEP', 'security': 3, 'created': 1548873938, 'public_key': '30819f300d06092a864886f70d010101050003818d0030818902818100adc437c186890233110a98090e78dbc35ed12c384576032346bc18e147802a819fdf4c08f48f37276f0c59714e06c30f577afbad13f94a2473b1deef1fbc99f9c25f60160198b8f3e402f1f12d64895d1a716adbbf5e592517d429cd91d7d7d59228a0544f7dd4e984647c3769e6636504fae80eaad49f8e76cb6a8399a6cc7f0203010001'}]

    app = WxAsyncApp()
    
    #dlg.Show()
    #wx.lib.inspection.InspectionTool().Show()
    algorithms = ['ENCRYPT_RSA_1024_OAEP', 'ENCRYPT_RSA_2048_OAEP', 'ENCRYPT_RSA_4096_OAEP', 'SIGN_RSA_1024_PKCS1_15', 'SIGN_RSA_2048_PKCS1_15', 'SIGN_RSA_4096_PKCS1_15', 'SIGN_ECDSA_P256_RFC6979', 'SIGN_ECDSA_secp192k1_RFC6979', 'SIGN_ECDSA_secp224k1_RFC6979', 'SIGN_ECDSA_secp256k1_RFC6979']
    
    async def dlg():
        dlg = KeyPickerDialog(KEYS,  algorithms=algorithms)
        result = await AsyncShowDialog(dlg)
        print ("res", dlg.GetValue())
    
    async def dlg2():
        dlg = NewKeyDialog(algorithms=algorithms)
        result = await AsyncShowDialog(dlg)

        

    loop = get_event_loop()
    loop.create_task(dlg())
    loop.run_until_complete(app.MainLoop())
