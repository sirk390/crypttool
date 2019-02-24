import winreg
REG_PATH = r"SOFTWARE\Crypttool\Settings"

class WinRegistry():
    @staticmethod
    def set(name, value):
        try:
            winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH)
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(registry_key, name, 0, winreg.REG_SZ, value)
            winreg.CloseKey(registry_key)
            return True
        except WindowsError:
            return False
    
    @staticmethod
    def get(name):
        try:
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0,
                                           winreg.KEY_READ)
            value, regtype = winreg.QueryValueEx(registry_key, name)
            winreg.CloseKey(registry_key)
            return value
        except WindowsError:
            return None
        
        


if __name__ == '__main__':
    #WinRegistry.set_setting("ABCD", "kjooji")
    print (WinRegistry.get_setting("ABCD"))