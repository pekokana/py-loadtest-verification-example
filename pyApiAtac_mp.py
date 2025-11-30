# --------------------------------------------------------------------------------------
# ファイル名: pyApiAtac_mp.py
# 概要: Python multiprocessingを使用したSOAP負荷テストクライアント。
# 目的: SOAPサービスへのリクエストの同時実行性（並列性）を検証するために作成。
#
# 作成者: Pekokana
# 作成日: 2025-11-30
# バージョン: 1.0.0
# --------------------------------------------------------------------------------------
# 実行方法：python pyApiAtac_mp.py
import multiprocessing as mp
import time
import http.client
import ssl

# --- 接続設定 ---
SERVICE_HOST = '127.0.0.1'      # ★ サービス提供サーバーのホスト名/IPアドレス
SERVICE_PATH = '/soap/endpoint'   # ★ サービスのエンドポイントパス
SERVICE_PORT = 8000                 # ★ ポート番号 (HTTPSの場合は443)
IS_HTTPS = False                  # ★ HTTPS (True) か HTTP (False) か
SOAP_ACTION_HEADER = 'http://ApiAtackDriverExampleProgram.com/IService/ApiMethod' # ★ SOAPActionヘッダーの値
SOAP_METHOD_NAME = 'ApiMethod'   # ★ SOAPリクエストXML内のメソッド名

# --- テスト設定 ---
BASE_PARAMETER_VALUE = 1000       # パラメータのベース値
DURATION_SECONDS = 10             # テスト実行時間（秒）
TARGET_RATE = 1000                  # １秒間に実行したい目標リクエスト数
TARGET_INTERVAL = 1.0 / TARGET_RATE # 1リクエストあたりの目標間隔

# --- SOAP XML テンプレート (修正) ---
# {param_value}: リクエストごとに変わるパラメータ値
# {request_id_tag}: P<プロセスID>-R<連番>形式の識別子を含むXMLタグを埋め込む
SOAP_ENVELOPE_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <{method_name} xmlns="http://ApiAtackDriverExampleProgram.com/">
      <requestParameter>{param_value}</requestParameter>
      {request_id_tag} 
    </{method_name}>
  </soap:Body>
</soap:Envelope>"""

# プロセスごとに実行する関数
def send_soap_request(request_count):
    """
    SOAPサービスにリクエストを送信する関数 (標準ライブラリのみ使用)
    """
    # multiprocessingの場合はプロセスID (PID) を取得
    process_id = mp.current_process().pid
    request_id_value = f"P{process_id}-R{request_count}" # 例: P12345-R10
    request_id_tag = f"<requestId>{request_id_value}</requestId>" # XMLタグ形式で生成
    
    # 2. パラメータ値の準備
    unique_param = BASE_PARAMETER_VALUE + request_count
    
    # 3. SOAP XMLの組み立て
    soap_body = SOAP_ENVELOPE_TEMPLATE.format(
        method_name=SOAP_METHOD_NAME,
        param_value=unique_param,
        request_id_tag=request_id_tag # 識別子をXMLに埋め込む
    ).encode('utf-8')
    
    # 4. HTTP接続の確立
    try:
        # ここからI/O処理
        if IS_HTTPS:
            conn = http.client.HTTPSConnection(SERVICE_HOST, SERVICE_PORT, context=ssl.create_default_context())
        else:
            conn = http.client.HTTPConnection(SERVICE_HOST, SERVICE_PORT)

        # 5. ヘッダーの定義
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "Content-Length": str(len(soap_body)),
            "SOAPAction": SOAP_ACTION_HEADER
        }

        # 6. リクエストの送信
        conn.request("POST", SERVICE_PATH, body=soap_body, headers=headers)
        
        # 7. レスポンスの受信
        response = conn.getresponse()
        
        # 8. 結果の処理
        if 200 <= response.status < 300:
            response_data = response.read().decode('utf-8')
            # ログに識別子を出力し、レスポンス本文も確認
            print(f"[{request_id_value}] SUCCESS. Param: {unique_param}, Status: {response.status}")
            # print(f"  Response Body Check: {response_data.strip()[:100]}...") # ロギングが多くなるためコメントアウト
        else:
            error_data = response.read().decode('utf-8')
            print(f"[{request_id_value}] FAILED. HTTP Status: {response.status}, Error: {error_data[:100]}")

        conn.close()

    except Exception as e:
        print(f"[{request_id_value}] CRITICAL ERROR. Param: {unique_param}, Error: {e}")

# メイン実行部分
def run_load_test():
    """
    ロードテストを実行する関数。
    """
    print(f"Starting load test for {DURATION_SECONDS} seconds against {SERVICE_HOST}:{SERVICE_PORT}...")
    print(f"Using multiprocessing. Total target rate: {TARGET_RATE} req/sec.")
    
    start_time = time.time()
    request_count = 0
    processes = []
    
    # テストの実行
    while (time.time() - start_time) < DURATION_SECONDS:
        request_count += 1
        
        iteration_start_time = time.time()
        
        # send_soap_requestには連番 (request_count) のみを渡します
        process = mp.Process(target=send_soap_request, args=(request_count,))
        processes.append(process)
        process.start()
        
        # 実行にかかった時間を計算
        execution_time = time.time() - iteration_start_time
        
        # 次のリクエストまでの待機時間を計算 (レート制御)
        sleep_time = TARGET_INTERVAL - execution_time
        
        if sleep_time > 0:
            time.sleep(sleep_time)
            
    # プロセスはスレッドより重いため、joinのタイムアウトは長めが推奨されることがあります
    for p in processes:
        p.join(timeout=10) # タイムアウトを10秒に延長
            
    end_time = time.time()
    
    actual_duration = end_time - start_time
    actual_rate = request_count / actual_duration
    
    print("\n--- Test Finished ---")
    print(f"Total Requests Sent: {request_count}")
    print(f"Duration: {actual_duration:.2f} seconds")
    print(f"Actual Rate: {actual_rate:.2f} requests/sec")

# 実行
if __name__ == "__main__":
    # multiprocessingを使用する場合、Windowsではこのブロックが必須です。
    run_load_test()