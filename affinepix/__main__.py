"""命令行入口:

  python -m affinepix run  <操作清单> --out <输出目录>
  python -m affinepix page <操作清单> --dir <输出目录> --html <页面文件>

退出码:0 成功;1 输入不可用;2 用法错误(argparse 默认)。
"""

import argparse
import sys

from . import runner


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="affinepix",
        description="24 位 BMP 的中心旋转与缩放(单次重采样)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="执行变换清单,写结果位图与 report.txt")
    p_run.add_argument("ops", help="变换清单路径")
    p_run.add_argument("--out", required=True, help="输出目录")

    p_page = sub.add_parser("page", help="用 run 的输出生成自包含对比页面")
    p_page.add_argument("ops", help="变换清单路径")
    p_page.add_argument("--dir", required=True, help="run 的输出目录")
    p_page.add_argument("--html", required=True, help="页面文件路径")
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "run":
            lines = runner.execute_run(args.ops, args.out)
            for line in lines:
                print(line)
        else:
            runner.execute_page(args.ops, args.dir, args.html)
            print("页面已写出: %s" % args.html)
    except runner.RunError as exc:
        print("错误: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
