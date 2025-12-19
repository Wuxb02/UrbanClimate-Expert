"""
测试运行脚本

快速运行不同类型的测试
"""
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str]) -> int:
    """运行命令并返回退出码"""
    print(f"\n{'='*60}")
    print(f"运行: {' '.join(cmd)}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode


def main():
    """主函数"""
    python_exe = r"D:\anaconda\python.exe"

    if len(sys.argv) > 1:
        test_type = sys.argv[1]
    else:
        test_type = "unit"

    if test_type == "all":
        print("运行所有测试...")
        return run_command([python_exe, "-m", "pytest", "-v"])

    elif test_type == "unit":
        print("运行单元测试...")
        return run_command([
            python_exe, "-m", "pytest",
            "tests/test_parser.py",
            "tests/test_documents.py",
            "tests/test_api_unit.py",
            "-v"
        ])

    elif test_type == "integration":
        print("运行集成测试...")
        print("注意: 集成测试需要配置 MySQL 数据库")
        return run_command([
            python_exe, "-m", "pytest",
            "tests/test_documents_integration.py",
            "-v", "--tb=short"
        ])

    elif test_type == "coverage":
        print("运行测试并生成覆盖率报告...")
        return run_command([
            python_exe, "-m", "pytest",
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html",
            "-v"
        ])

    elif test_type == "quick":
        print("快速测试(仅单元测试,无覆盖率)...")
        return run_command([
            python_exe, "-m", "pytest",
            "tests/test_parser.py",
            "tests/test_documents.py",
            "tests/test_api_unit.py",
            "-v", "--tb=short", "-q"
        ])

    elif test_type == "parser":
        print("仅测试 PDF 解析...")
        return run_command([
            python_exe, "-m", "pytest",
            "tests/test_parser.py",
            "-v"
        ])

    elif test_type == "documents":
        print("仅测试文档 API...")
        return run_command([
            python_exe, "-m", "pytest",
            "tests/test_documents.py",
            "tests/test_api_unit.py",
            "-v"
        ])

    else:
        print(f"未知的测试类型: {test_type}")
        print("\n可用的测试类型:")
        print("  all         - 运行所有测试")
        print("  unit        - 运行单元测试(默认)")
        print("  integration - 运行集成测试(需要数据库)")
        print("  coverage    - 运行测试并生成覆盖率报告")
        print("  quick       - 快速测试(无覆盖率)")
        print("  parser      - 仅测试 PDF 解析")
        print("  documents   - 仅测试文档 API")
        print("\n用法:")
        print(f"  {python_exe} run_tests.py [test_type]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
