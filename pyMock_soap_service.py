# --------------------------------------------------------------------------------------
# ファイル名: pyMock_soap_service.py
# 概要: Python標準ライブラリを使用したシンプルなSOAPモックサーバー。
# 目的: 負荷テストクライアントからの大量の同時接続（マルチプロセス/スレッド）
#       を受け付け、リクエストIDを検証するために使用。
#
# 技術詳細: socketserver.ThreadingTCPServer を使用し、接続ごとにスレッドを生成。
#
# 作成者: Pekokana
# 作成日: 2025-11-30
# バージョン: 1.0.0
# --------------------------------------------------------------------------------------
import http.server
import socketserver
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import time
import datetime # datetimeモジュールを追加
# import re # reモジュールは不要になりました

# --- サービス設定 (テストツールと一致させる必要があります) ---
HOST = "127.0.0.1"
PORT = 8000
SERVICE_PATH = "/soap/endpoint"
SOAP_METHOD_NAME = 'ApiMethod'
PARAM_TAG_NAME = 'requestParameter'
REQUEST_ID_TAG_NAME = 'requestId'

# XMLの名前空間を定義 (レスポンス構築とリクエスト解析に使用)
TARGET_NAMESPACE = 'http://tempuri.org/'
SOAP_NAMESPACE = 'http://schemas.xmlsoap.org/soap/envelope/'

# --- SOAP レスポンス テンプレート (修正) ---
# {received_request_id} にクライアントから受け取った識別子を埋め込む
SOAP_RESPONSE_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
    <soap:Body>
        <{method_name}Response xmlns="{target_namespace}">
            <{method_name}Result>
                <status>SUCCESS</status>
                <receivedParam>{received_param}</receivedParam>
                <timestamp>{timestamp}</timestamp>
                <received_request_id>{received_request_id}</received_request_id>
            </{method_name}Result>
        </{method_name}Response>
    </soap:Body>
</soap:Envelope>"""


class SOAPHandler(http.server.BaseHTTPRequestHandler):
    """
    HTTPリクエストを処理し、SOAPレスポンスを返すハンドラ
    """
    SOAP_NAMESPACE = 'http://schemas.xmlsoap.org/soap/envelope/'
    TARGET_NAMESPACE = 'http://tempuri.org/'

    def do_POST(self):
        # 1. URLパスのチェック
        parsed_url = urlparse(self.path)
        if parsed_url.path != SERVICE_PATH:
            self._send_error(404, "Not Found")
            return

        # 2. リクエストボディの読み込み
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        # 3. SOAP XMLの解析
        received_param = None
        received_request_id = "N/A" # 識別子を初期化
        current_time_stamp = time.time() # UNIXタイムスタンプを取得
        readable_time = datetime.datetime.fromtimestamp(current_time_stamp).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] # 人間が読める形式に変換
        
        try:
            # XML文字列をElementTreeオブジェクトにパース
            root = ET.fromstring(post_data)
            
            # クライアントのSOAP XMLテンプレートから名前空間を定義
            CLIENT_TARGET_NAMESPACE = 'http://ApiAtackDriverExampleProgram.com/'
            
            # 3a. SOAP Body要素の検索
            body_xpath = f"{{{self.SOAP_NAMESPACE}}}Body"
            body_element = root.find(body_xpath)
            if body_element is None:
                raise ValueError("SOAP Body element not found.")

            # 3b. メソッド要素の検索
            method_xpath_client = f"{{{CLIENT_TARGET_NAMESPACE}}}{SOAP_METHOD_NAME}"
            method_element = body_element.find(method_xpath_client)
            if method_element is None:
                method_element = body_element.find(SOAP_METHOD_NAME)
            if method_element is None:
                raise ValueError(f"Method tag <{SOAP_METHOD_NAME}> not found with namespaces.")

            # 3c. パラメータ要素の検索
            param_element = method_element.find(f"{{{CLIENT_TARGET_NAMESPACE}}}{PARAM_TAG_NAME}")
            if param_element is None:
                param_element = method_element.find(PARAM_TAG_NAME)
            if param_element is None:
                raise ValueError(f"Parameter tag <{PARAM_TAG_NAME}> not found.")

            received_param = param_element.text
            
            # # 3d. リクエストID要素の検索
            # request_id_element = method_element.find(f"{{{CLIENT_TARGET_NAMESPACE}}}{REQUEST_ID_TAG_NAME}")
            # if request_id_element is None:
            #     request_id_element = method_element.find(REQUEST_ID_TAG_NAME)
            
            # if request_id_element and request_id_element.text:
            #     received_request_id = request_id_element.text

            # 3d. リクエストID要素の検索 (より堅牢な検索に修正) 
            # 1. 名前空間付きで検索 (pyApiAtac.pyのリクエスト構造と一致するはず)
            request_id_element = method_element.find(f"{{{CLIENT_TARGET_NAMESPACE}}}{REQUEST_ID_TAG_NAME}")
            
            # 2. 見つからなかった場合、名前空間なしで検索
            if request_id_element is None:
                request_id_element = method_element.find(REQUEST_ID_TAG_NAME)
            
            # 3. リクエストIDが他の名前空間を持つ可能性がある場合（例えば、リクエストIDがデフォルト名前空間なしで定義されている場合）
            # ここは必須ではありませんが、より汎用的にするためにコメントアウトで例示
            # if request_id_element is None:
            #     # 全ての子要素をイテレートしてタグ名で確認
            #     for child in method_element:
            #         # タグ名がREQUEST_ID_TAG_NAME ('requestId')で終わるか確認
            #         if child.tag.endswith(REQUEST_ID_TAG_NAME):
            #             request_id_element = child
            #             break
            
            if request_id_element is not None and request_id_element.text is not None:
                received_request_id = request_id_element.text
            # else:
            #     # デバッグ用: なぜ見つからなかったかをログに出す
            #     print(f"DEBUG: requestId tag not found. Children tags of ApiMethod: {[c.tag for c in method_element]}")


        except Exception as e:
            # XMLパースエラーが発生した場合
            print(f"[{readable_time}] XML Parsing Error: {e}")
            self._send_error(400, f"Bad Request: XML Parsing failed. Error: {e}")
            return
        
        # 4. レスポンスの組み立て
        # 処理シミュレーションのためのわずかな遅延
        # time.sleep(0.001) 
        
        response_body = SOAP_RESPONSE_TEMPLATE.format(
            method_name=SOAP_METHOD_NAME,
            target_namespace=self.TARGET_NAMESPACE,
            received_param=received_param,
            timestamp=current_time_stamp,
            received_request_id=received_request_id 
        ).encode('utf-8')

        # 5. レスポンスの送信
        self.send_response(200)
        self.send_header("Content-type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

        # ログ出力
        print(f"[{readable_time}] [OK] Request ID: {received_request_id}, Param: {received_param}")


    def _send_error(self, code, message):
        """エラー応答を送信するヘルパー関数"""
        self.send_response(code)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(f"<h1>{code} {message}</h1>".encode('utf-8'))
        print(f"[ERROR] Sent {code} response.")


def run_mock_service():
    """モックSOAPサービスを起動する関数"""
    # ThreadingTCPServerで同時接続に対応
    try:
        with socketserver.ThreadingTCPServer((HOST, PORT), SOAPHandler) as httpd:
            print(f"--- Mock SOAP Service Started ---")
            print(f"Listening on http://{HOST}:{PORT}{SERVICE_PATH}")
            print(f"Press Ctrl+C to stop.")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n--- Mock SOAP Service Stopped ---")
    except Exception as e:
        print(f"\nServer error: {e}")

if __name__ == "__main__":
    # XML解析時に発生する可能性のある問題を回避するため、名前空間を登録しておきます
    ET.register_namespace('', TARGET_NAMESPACE)
    run_mock_service()