"""
综合交通仿真系统 (CITY)

主入口文件，提供命令行接口运行仿真。
"""

import argparse
import sys

from examples.simple_intersection import run_simple_simulation
from examples.grid_city import run_grid_simulation


def main():
    """主函数。"""
    parser = argparse.ArgumentParser(
        description='综合交通仿真系统 (CITY)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python main.py --example simple           # 运行简单交叉口仿真
  python main.py --example grid             # 运行网格城市仿真
  python main.py --visual simple            # 可视化简单交叉口
  python main.py --visual grid              # 可视化网格城市
  python main.py --test                    # 运行测试
        '''
    )

    parser.add_argument(
        '--example',
        choices=['simple', 'grid'],
        default='simple',
        help='选择要运行的示例 (默认: simple)'
    )

    parser.add_argument(
        '--visual',
        choices=['simple', 'grid'],
        help='运行可视化仿真'
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='运行测试套件'
    )

    args = parser.parse_args()

    if args.test:
        print("运行测试套件...")
        run_tests()
    elif args.visual == 'simple':
        from examples.visual_simple import main as visual_main
        visual_main()
    elif args.visual == 'grid':
        from examples.visual_grid import main as visual_main
        visual_main()
    elif args.example == 'simple':
        run_simple_simulation()
    elif args.example == 'grid':
        run_grid_simulation()


def run_tests():
    """运行所有测试。"""
    print("=" * 60)
    print("运行测试套件")
    print("=" * 60)

    tests = [
        ('向量工具', 'tests.test_vector'),
        ('道路网络', 'tests.test_road_network'),
        ('智能体', 'tests.test_agents'),
    ]

    for name, module in tests:
        print(f"\n运行 {name} 测试...")
        try:
            mod = __import__(module, fromlist=['run_all_tests'])
            mod.run_all_tests()
        except Exception as e:
            print(f"  ✗ 测试失败: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
