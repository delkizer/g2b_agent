from config.config import Config


def main():
    config = Config()
    print("=== Server Config 검증 ===")
    print(f"Database URL: {config.database_url}")
    print(f"Notion Min Score: {config.notion_min_score}")
    print("=== Config 로드 성공! ===")


if __name__ == "__main__":
    main()
