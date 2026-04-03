import win32com.client
import time

try:
    canoe_app = win32com.client.Dispatch("CANoe.Application")
    measurement = canoe_app.Measurement
except Exception as e:
    print(f"Error connecting to CANoe: {e}")
    print("Please ensure CANoe is installed and running, and try again.")
    exit()

if not measurement.Running:
    measurement.Start()
    print("CANoe measurement started.")
    # 增加启动后的延时，确保CANoe完全准备好
    time.sleep(15)  # 尝试增加到10秒或15秒

try:
    capl_function = canoe_app.CAPL.GetFunction("sendCANMessage")
    if capl_function:
        print("Successfully obtained CAPL function 'sendCANMessage'.")
    else:
        print("Error: CAPL function 'sendCANMessage' not found. This should not happen if CAPL file is correct.")
        exit()

    message_id_1 = 0x651
    data_1 = [0xFF, 0x00]
    print(f"Python: Attempting to send message ID=0x{message_id_1:X}, Data={data_1}")
    capl_function.Call(message_id_1, data_1)
    print(f"Python: Sent message ID=0x{message_id_1:X}, Data={data_1}")

    time.sleep(2)

    message_id_2 = 0x651
    data_2 = [0xAA, 0xBB]
    print(f"Python2: Attempting to send message ID=0x{message_id_2:X}, Data={data_2}")
    capl_function.Call(message_id_2, data_2)
    print(f"Python2: Sent message ID=0x{message_id_2:X}, Data={data_2}")

except Exception as e:
    print(f"An error occurred during CAPL function call: {e}")
    print("This usually means the CAPL function was not accessible via COM at the time of the call.")
    print("Possible reasons: CANoe not fully initialized, or CAPL file not correctly loaded/compiled in the active configuration.")