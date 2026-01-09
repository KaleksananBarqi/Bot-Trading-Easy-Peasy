import sys
import os

# Tambahkan src ke path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    import openai
    print("[OK] Library 'openai' berhasil diimport.")
except ImportError:
    print("[FAIL] Gagal import 'openai'. Pastikan sudah diinstall.")
    sys.exit(1)

try:
    from src.modules.ai_brain import AIBrain
    import config
    
    print(f"[INFO] Config AI_MODEL_NAME: {config.AI_MODEL_NAME}")
    
    brain = AIBrain()
    if brain.client:
        print("[OK] AIBrain berhasil diinisialisasi dengan Client.")
        print(f"[INFO] Base URL: {brain.client.base_url}")
    else:
        print("[WARN] AIBrain diinisialisasi tanpa Client (API Key missing?).")

except Exception as e:
    print(f"[FAIL] Error saat inisialisasi AIBrain: {e}")
    sys.exit(1)
