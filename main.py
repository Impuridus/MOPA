import webview


if __name__ == "__main__":
    webview.create_window(
        title="MOPA",
        url="ui/index.html",
        width=1000,
        height=700,
    )

    webview.start()