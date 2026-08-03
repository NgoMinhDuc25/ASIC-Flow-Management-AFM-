import os
import subprocess


USERNAME = "NgoMinhDuc25"
REPO_NAME = "All_My_Useful_Scripts_PRIVATE"

def process_pull_usefull_scripts(LOCAL_DIR, PAT_TOKEN, USERNAME, REPO_NAME):
    REPO_URL = f"https://{PAT_TOKEN}@github.com/{USERNAME}/{REPO_NAME}.git"

    # Kiểm tra xem thư mục đã tồn tại và là repo Git hay chưa
    if os.path.exists(LOCAL_DIR) and os.path.exists(os.path.join(LOCAL_DIR, ".git")):
        print("Đang thực hiện git pull...")
        
        # Cập nhật lại URL origin để đảm bảo dùng PAT mới nhất
        subprocess.run(
            ["git", "remote", "set-url", "origin", REPO_URL],
            cwd=LOCAL_DIR,
            capture_output=True,
            text=True
        )

        # Chạy git pull đơn giản
        result = subprocess.run(
            ["git", "pull"],
            cwd=LOCAL_DIR,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("Pull thành công!\n", result.stdout)
            return {
                "msg": "Pull success",
                "status": True
            }
        else:
            # Mask token trong stderr để tránh lộ thông tin nhạy cảm
            clean_error = result.stderr.replace(PAT_TOKEN, "***")
            print("Lỗi khi pull:\n", clean_error)
            return {
                "msg": f"Pull failed: {clean_error.strip()}",
                "status": False
            }
            
    else:
        print("Đang thực hiện git clone...")
        result = subprocess.run(
            ["git", "clone", REPO_URL, LOCAL_DIR],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("Clone thành công!\n", result.stdout)
            return {
                "msg": "Clone success",
                "status": True
            }
        else:
            clean_error = result.stderr.replace(PAT_TOKEN, "***")
            print("Lỗi khi clone:\n", clean_error)
            return {
                "msg": f"Clone failed: {clean_error.strip()}",
                "status": False
            }