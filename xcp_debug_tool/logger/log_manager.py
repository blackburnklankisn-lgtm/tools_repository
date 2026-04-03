import logging
import sys

# 临时简单的 logger，后面在 logging 模块中再完善
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("XCP_Debug_Tool")
