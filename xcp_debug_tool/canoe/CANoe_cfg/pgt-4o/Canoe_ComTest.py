import win32com.client

try:
   canoe_app = win32com.client.Dispatch("CANoe.Application")
   print("CANoe COM接口已启用！")
except Exception as e:
   print(f"无法访问CANoe COM接口：{e}")