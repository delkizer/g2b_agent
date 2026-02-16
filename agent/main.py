from config.config import Config

def main():
    config = Config()
    print("=== Agent Config 검증 ===")
    print(f"G2B API Base URL: {config.g2b_api_base_url}")
    print(f"Claude Model: {config.claude_model}")
    print(f"Claude Max Tokens: {config.claude_max_tokens}")
    print(f"Schedule Interval: {config.schedule_interval_minutes}분")
    print(f"EC2 API URL: {config.ec2_api_url}")
    print("=== Config 로드 성공! ===")

if __name__ == "__main__":
    main()
