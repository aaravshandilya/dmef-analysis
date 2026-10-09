# GitHub and public app deployment

## GitHub and Windows

The current project is already in
[aaravshandilya/dmef-analysis](https://github.com/aaravshandilya/dmef-analysis).
In VS Code choose **Clone Git Repository**, paste
`https://github.com/aaravshandilya/dmef-analysis.git`, and open the downloaded
folder. GitHub sign-in may be required because the repository is private.
On Windows, double-click `run_windows.bat` in that folder. The launcher creates
`.venv`, installs dependencies from `requirements.txt`, and starts Streamlit.
You can stop the app with Ctrl+C in the command window.

The `.venv` folder is ignored. No secrets are needed by the app.

Use a **private repository** if the source photographs must remain restricted.
Review the included research images and result files before making a repository
public. A public testing app can be deployed from a private repository with
the appropriate Streamlit Community Cloud access and app visibility settings.

## Streamlit Community Cloud

1. Sign in at https://share.streamlit.io and connect the GitHub account that
   owns the repository.
2. Create an app using repository `aaravshandilya/dmef-analysis`, branch `main`,
   and entrypoint `app.py`.
3. Set the app's visibility to **Public** and verify the resulting
   `*.streamlit.app` URL in a signed-out browser window.
4. Upload one of the JPEGs in `data/raw` to test the published app. Optionally
   upload `sample_plate_map.csv` as the plate map.

The public app processes images uploaded by visitors. Its annotations are
unverified image features, not clinical diagnoses. Anyone with the public URL
can upload an image; avoid uploading identifiable or sensitive records.
