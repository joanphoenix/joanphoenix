"""Mac-specific configuration without changing the Windows entry point."""
import copy

from .framework import load_framework


def build_config(language="en_US"):
    load_framework()
    from config import config
    result = copy.deepcopy(config)
    for key in ("windows", "update_pyappify", "custom_tabs", "blur_area"):
        result.pop(key, None)
    result.update(gui=None, custom_tasks=False, config_folder="configs-macos",
                  locale=language, macos_game_language=language,
                  log_file="logs/ok-ww-macos.log", error_log_file="logs/ok-ww-macos-error.log")
    result["ocr"]["params"].update(use_openvino=False, use_npu=False)
    result["onetime_tasks"] = [item for item in result["onetime_tasks"]
                               if item[1] != "MultiAccountDailyTask"]
    # These upstream tasks declare Chinese-only UI recognition.
    result["onetime_tasks"] = [item for item in result["onetime_tasks"]
                               if not (item[1] == "ChangeEchoTask" and language != "zh_CN")
                               and not (item[1] == "EnhanceEchoTask" and language not in ("zh_CN", "zh_TW"))]
    result["trigger_tasks"] = [item for item in result["trigger_tasks"]
                               if item[1] != "MouseResetTask"]
    return result
