# GitHub and public app deployment

## GitHub and Windows

The project is in the public
[aaravshandilya/dmef-analysis](https://github.com/aaravshandilya/dmef-analysis)
repository. Open a clone of the repository in VS Code and
double-click `run_windows.bat` to run it locally at `http://localhost:8502`.
The launcher creates `.venv` and installs dependencies. Stop the app with
Ctrl+C in its command window.

The `.venv` folder is ignored. No secrets are needed by the app.

## Streamlit Community Cloud

1. Sign in at https://share.streamlit.io and connect the GitHub account that
   owns the repository.
2. Create an app using repository `aaravshandilya/dmef-analysis`, branch `main`,
   and entrypoint `app.py`.
3. Set the app's visibility to **Public** and verify the resulting
   `*.streamlit.app` URL in a signed-out browser window.
4. Upload a JPEG with white loops drawn around background areas to test the
   circled-background analysis. Optionally upload `sample_plate_map.csv`.

The public app processes images uploaded by visitors. Its annotations are
unverified image features, not clinical diagnoses. Anyone with the public URL
can upload an image; avoid uploading identifiable or sensitive records.
