# Controller Logger 初期セットアップガイド

## 1. 前提条件
- **OS**：Windows 10/11（pygame は Windows, Mac, Linux 対応）
- **Python**：3.10 以上推奨
- **ゲームパッド**：USB 接続可能なもの（Xbox, DualShock, ジョイスティック 等）

---

## 2. Python 環境準備
1. Python がインストールされているか確認：
```bash
python --version
```

- バージョンが表示されれば OK
- 表示されなければ [Python公式サイト](https://www.python.org/downloads/)からダウンロードしてインストールしてください
- インストール時に「Add Python to PATH」にチェックを入れること



## 3. ライブラリのインストール
```
pip install -r requirements.txt
```

## 4. アプリ実行
```
# アプリを起動
python main.py

# GUI が起動します
# 「記録開始」をクリック → CSV にデータを保存しながら仮想コントローラーが画面に表示
# 「記録停止」をクリック → 保存終了
```
