# GitHub and public app deployment

## GitHub

The working project has local Git history. A downloaded ZIP does not include
the `.git` directory, so initialize it before pushing. Keep `app.py`, `bright_regions.py`,
`requirements.txt`, `data/raw`, and the sample CSV files in the repository.
The `.venv` folder is ignored. No secrets are needed by the app.

To publish the extracted ZIP from Windows, first create an **empty** repository
named `dmef-analysis` in your GitHub account (leave the GitHub README and
`.gitignore` options unchecked). In PowerShell inside the extracted
`dmef-analysis` folder, run:

```powershell
git init -b main
git add .
git commit -m "Add DMEF image analysis app"
git remote add origin https://github.com/YOUR_USERNAME/dmef-analysis.git
git push -u origin main
```

Use a **private repository** if the source photographs must remain restricted.
Review the included research images and result files before making a repository
public. A public testing app can be deployed from a private repository with
the appropriate Streamlit Community Cloud access and app visibility settings.

## Streamlit Community Cloud

1. Sign in at https://share.streamlit.io and connect the GitHub account that
   owns the repository.
2. Create an app using repository `YOUR_USERNAME/dmef-analysis`, branch `main`,
   and entrypoint `app.py`.
3. Set the app's visibility to **Public** and verify the resulting
   `*.streamlit.app` URL in a signed-out browser window.
4. Upload one of the JPEGs in `data/raw` to test the published app. Optionally
   upload `sample_plate_map.csv` as the plate map.

The public app processes images uploaded by visitors. Its annotations are
unverified image features, not clinical diagnoses. Anyone with the public URL
can upload an image; avoid uploading identifiable or sensitive records.
