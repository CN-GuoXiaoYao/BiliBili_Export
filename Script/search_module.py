import logging
from pathlib import Path


class AdvancedSearchEngine:
    @staticmethod
    def search_cache(keyword, progress_callback, cache_root:str):
        """执行缓存搜索（支持BV号/路径/标题）"""
        logging.getLogger('SearchModule').info(f"开始搜索：{keyword}")
        record_file = Path(__file__).parent / "downloaded.txt"
        results = []
        keyword = keyword.lower()  # 统一转为小写

        try:
            with open(record_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                total = len(lines)

                for idx, line in enumerate(lines):
                    progress = int((idx + 1) / total * 100)
                    progress_callback(progress)

                    parts = line.strip().split("|")
                    if len(parts) != 3:
                        continue

                    bvid, folder, title = parts
                    if folder == "网络":
                        full_path = "网络下载"
                    elif folder[:5] == "文件下载_":
                        full_path = folder
                    else:
                        full_path = str(Path(cache_root) / folder)

                    # 检查所有字段
                    if (keyword in bvid.lower() or
                            keyword in full_path.lower() or
                            keyword in title.lower()):
                        results.append({
                            "bvid": bvid,
                            "path": full_path,
                            "title": title
                        })

        except FileNotFoundError:
            logging.error("下载记录文件不存在")
        except Exception as e:
            logging.error(f"搜索失败：{str(e)}")

        return results