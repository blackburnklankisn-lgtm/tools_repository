try:
    print(bytes([int(x) & 0xFF for x in (1000, -500)]))
    print("SUCCESS")
except Exception as e:
    print(repr(e))
