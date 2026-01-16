"""
Phase C2: 快速 API 测试脚本

等待服务启动并进行基本的 API 测试
"""

import time
import requests
import json

API_BASE = "http://localhost:8000"

def wait_for_service(timeout=60):
    """等待服务启动"""
    print("⏳ 等待 Embedding API 服务启动...")
    print(f"   超时时间: {timeout} 秒")

    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{API_BASE}/api/health", timeout=2)
            if response.status_code == 200:
                data = response.json()
                if data.get('model_loaded'):
                    print("\n✅ 服务已就绪！")
                    print(f"   状态: {data['status']}")
                    print(f"   模型: {data['model_loaded']}")
                    print(f"   缓存: {data['cache_connected']}")
                    return True
        except:
            pass

        elapsed = int(time.time() - start_time)
        print(f"   等待中... {elapsed} 秒", end='\r')
        time.sleep(2)

    print(f"\n❌ 服务启动超时 ({timeout} 秒)")
    return False

def test_coordinate_api():
    """测试坐标转换 API"""
    print("\n" + "=" * 60)
    print("🧪 测试坐标转换 API")
    print("=" * 60)

    test_cases = [
        {
            "text": "粗糙的声音",
            "prism_id": "texture",
            "description": "测试质感棱镜"
        },
        {
            "text": "合成器音色",
            "prism_id": "source",
            "description": "测试来源棱镜"
        }
    ]

    for test in test_cases:
        print(f"\n📝 {test['description']}")
        print(f"   文本: {test['text']}")
        print(f"   棱镜: {test['prism_id']}")

        try:
            start_time = time.time()
            response = requests.post(
                f"{API_BASE}/api/embed/coordinate",
                json={
                    "text": test['text'],
                    "prism_id": test['prism_id']
                },
                timeout=10
            )

            duration = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()
                x, y = data['x'], data['y']

                print(f"   ✅ 成功")
                print(f"   坐标: ({x:.2f}, {y:.2f})")
                print(f"   耗时: {duration:.1f}ms")

                # 验证坐标范围
                if 0 <= x <= 100 and 0 <= y <= 100:
                    print(f"   ✅ 坐标在有效范围内")
                else:
                    print(f"   ⚠️  坐标超出范围: ({x:.2f}, {y:.2f})")
            else:
                print(f"   ❌ 失败: HTTP {response.status_code}")
                print(f"   详情: {response.text}")

        except Exception as e:
            print(f"   ❌ 错误: {e}")

def test_batch_api():
    """测试批量转换 API"""
    print("\n" + "=" * 60)
    print("🧪 测试批量转换 API")
    print("=" * 60)

    try:
        start_time = time.time()
        response = requests.post(
            f"{API_BASE}/api/embed/batch",
            json={
                "texts": ["粗糙", "光滑", "明亮", "温暖"],
                "prism_id": "texture"
            },
            timeout=30
        )

        duration = (time.time() - start_time) * 1000

        if response.status_code == 200:
            data = response.json()
            coordinates = data['coordinates']
            count = data['count']

            print(f"\n   文本数量: {count}")
            print(f"   总耗时: {duration:.1f}ms")
            print(f"   平均每个: {duration/count:.1f}ms")
            print(f"\n   结果:")
            for coord in coordinates:
                print(f"      {coord['text']}: ({coord['x']:.2f}, {coord['y']:.2f})")

            print(f"\n   ✅ 批量转换成功")
        else:
            print(f"   ❌ 失败: HTTP {response.status_code}")

    except Exception as e:
        print(f"   ❌ 错误: {e}")

def main():
    """主函数"""
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "Embedding API 快速测试" + " " * 28 + "║")
    print("╚" + "═" * 58 + "╝")

    # 等待服务启动
    if not wait_for_service():
        print("\n💡 请先启动服务:")
        print("   cd data-pipeline")
        print("   python embedding_service.py")
        return

    # 测试坐标转换
    test_coordinate_api()

    # 测试批量转换
    test_batch_api()

    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)
    print("\n💡 下一步:")
    print("   1. 检查坐标计算结果是否符合预期")
    print("   2. 验证与本地计算的一致性")
    print("   3. 集成到客户端")
    print()

if __name__ == "__main__":
    main()
