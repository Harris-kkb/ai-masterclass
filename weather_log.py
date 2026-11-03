
def update_google_sheets(payload):

    sheet_1 = os.environ.get("SHEET_URL")
    sheet_2 = os.environ.get("SHEET_URL_2")

    active_urls = [
        url.strip()
        for url in [sheet_1, sheet_2]
        if url and url.strip()
    ]

    if not active_urls:
        raise SystemExit("No Google Sheet URLs configured")

    successful_updates = 0

    for index, sheet_url in enumerate(active_urls, start=1):

        try:
            response = requests.post(
                sheet_url,
                json=payload,
                timeout=60
            )

            print(
                f"Sheet {index} response: "
                f"{response.status_code} - {response.text}"
            )

            response.raise_for_status()

            if response.text.strip() != "OK":
                raise RuntimeError(
                    f"Unexpected response from Sheet {index}: "
                    f"{response.text}"
                )

            successful_updates += 1

        except Exception as error:
            raise SystemExit(
                f"Google Sheet {index} update failed: {error}"
            )

    print(
        f"Successfully updated "
        f"{successful_updates} Google Sheet(s)."
    )
