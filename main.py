# 便捷入口：python main.py 等价于 python -m arxiv_tracker.cli run --config config.yaml
import sys, subprocess
subprocess.run([sys.executable, "-m", "arxiv_tracker.cli", "run", "--config", "config.yaml"], check=False)
