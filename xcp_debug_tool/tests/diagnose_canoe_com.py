"""
CANoe COM 接口诊断脚本
用于排查 CAPL 函数无法通过 COM 访问的问题
请在 CANoe Measurement 运行状态下执行此脚本
"""
import win32com.client
import sys

def main():
    print("=" * 60)
    print("CANoe COM 诊断工具")
    print("=" * 60)

    # 1. 连接 CANoe
    try:
        app = win32com.client.Dispatch("CANoe.Application")
        print(f"[OK] CANoe 连接成功, 版本: {app.Version}")
    except Exception as e:
        print(f"[FAIL] 无法连接 CANoe: {e}")
        return

    # 2. 检查 Measurement 状态
    try:
        running = app.Measurement.Running
        print(f"[INFO] Measurement Running = {running}")
    except Exception as e:
        print(f"[FAIL] 无法读取 Measurement 状态: {e}")

    # 3. 尝试方法1: app.CAPL.GetFunction
    print("\n--- 方法 1: app.CAPL.GetFunction ---")
    try:
        capl_obj = app.CAPL
        print(f"[OK] app.CAPL 对象存在, type = {type(capl_obj)}")
        try:
            func = capl_obj.GetFunction("XCP_SendBytes")
            print(f"[OK] 找到函数 XCP_SendBytes: {func}")
        except Exception as e:
            print(f"[FAIL] GetFunction('XCP_SendBytes') 失败: {e}")
    except Exception as e:
        print(f"[FAIL] app.CAPL 不存在: {e}")

    # 4. 尝试方法2: 带节点名前缀
    print("\n--- 方法 2: 带节点名前缀 ---")
    node_names = ["caplTest", "ECU 1", "ECU1"]
    for node in node_names:
        for sep in [".", "::", "/"]:
            full_name = f"{node}{sep}XCP_SendBytes"
            try:
                func = app.CAPL.GetFunction(full_name)
                print(f"[OK] 找到函数 '{full_name}': {func}")
            except Exception as e:
                print(f"[FAIL] '{full_name}': {type(e).__name__}")

    # 5. 尝试方法3: app.System.Namespaces
    print("\n--- 方法 3: app.System.Namespaces ---")
    try:
        sys_ns = app.System.Namespaces
        print(f"[OK] System.Namespaces 对象存在")
        try:
            count = sys_ns.Count
            print(f"[INFO] Namespace 数量: {count}")
            for i in range(1, count + 1):
                ns = sys_ns.Item(i)
                print(f"  Namespace[{i}]: {ns.Name}")
        except Exception as e:
            print(f"[WARN] 无法枚举 Namespaces: {e}")
    except Exception as e:
        print(f"[FAIL] System.Namespaces 不存在: {e}")

    # 6. 尝试方法4: app.Networks (枚举网络节点)
    print("\n--- 方法 4: app.Networks ---")
    try:
        networks = app.Networks
        print(f"[OK] Networks 对象存在")
        try:
            count = networks.Count
            print(f"[INFO] Network 数量: {count}")
            for i in range(1, count + 1):
                net = networks.Item(i)
                print(f"  Network[{i}]: {net.Name}")
                try:
                    nodes = net.Nodes
                    for j in range(1, nodes.Count + 1):
                        node = nodes.Item(j)
                        print(f"    Node[{j}]: {node.Name}")
                except Exception as e2:
                    print(f"    无法枚举节点: {e2}")
        except Exception as e:
            print(f"[WARN] 无法枚举 Networks: {e}")
    except Exception as e:
        print(f"[FAIL] Networks 不存在: {e}")

    # 7. 尝试方法5: 通过 Environment
    print("\n--- 方法 5: app.Environment ---")
    try:
        env = app.Environment
        print(f"[OK] Environment 对象存在, type = {type(env)}")
        try:
            vars_obj = env.Variables
            print(f"[OK] Environment.Variables 存在")
        except:
            pass
    except Exception as e:
        print(f"[FAIL] Environment 不存在: {e}")

    # 8. 尝试方法6: 使用 EnsureDispatch (早期绑定)
    print("\n--- 方法 6: 使用 EnsureDispatch ---")
    try:
        app2 = win32com.client.gencache.EnsureDispatch("CANoe.Application")
        print(f"[OK] EnsureDispatch 成功, type = {type(app2)}")
        try:
            func = app2.CAPL.GetFunction("XCP_SendBytes")
            print(f"[OK] EnsureDispatch 方式找到函数: {func}")
        except Exception as e:
            print(f"[FAIL] EnsureDispatch 方式失败: {e}")
    except Exception as e:
        print(f"[FAIL] EnsureDispatch 失败: {e}")

    print("\n" + "=" * 60)
    print("诊断完成，请将以上全部输出发送给开发者。")
    print("=" * 60)

if __name__ == "__main__":
    main()
