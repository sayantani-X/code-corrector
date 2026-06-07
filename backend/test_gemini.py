from src.core.config import settings
from src.core.llm import generate_content_with_retry, get_client


def main() -> None:
    print("Testing Gemini API...")
    print(f"Project ID: {settings.gcp_project_id}")
    print(f"Region: {settings.gcp_region}")
    print("-" * 30)

    try:
        client = get_client()
        # Using Flash for a quick, cheap test
        response = generate_content_with_retry(
            client=client,
            model=settings.gemini_flash_model,
            prompt=(
                "Respond with exactly: 'Hello from Gemini! "
                "Authentication is working.' and nothing else."
            ),
        )
        print("Success! Response received:\n")
        print(response)
    except Exception as e:
        print(
            "\nError connecting to Gemini. Ensure you have run "
            "'gcloud auth application-default login' and your project "
            "ID is correct."
        )
        print("Details:", e)


if __name__ == "__main__":
    main()
