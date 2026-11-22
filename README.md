# FitStart Planner

A browser-based planner for a couple's nutrition, meals, recipes, workouts, and progress tracking.

## Live app

https://fitstartnp.github.io/fitstart/

The site is hosted by GitHub Pages from the `main` branch, repository root. The entry point is `index.html`.

## Included features

- Separate husband and wife profiles with metric/imperial unit options
- Estimated BMI, BMR, TDEE, calorie targets, and macronutrients
- Food and meal logging, recipes, meal ideas, and grocery planning
- Workout routines, exercise logs, set tracking, and rest timer
- Progress check-ins, charts, and couple progress views
- Browser-local persistence, JSON backup/export and import, and optional device PIN

Nutrition and energy calculations are estimates, not medical measurements or treatment advice.

## Hosting and dependencies

This is a static, single-page application. It does not require a server for local use or GitHub Pages hosting. It loads Tailwind CSS, Chart.js, and Google Fonts from their public CDNs, so an internet connection is needed for those external resources.

To deploy changes, update `index.html` on the `main` branch. GitHub Pages serves the repository root.

## Data and privacy

- By default, profile data is saved in the current browser's `localStorage`. It does not automatically move to another browser or device.
- Use **Export JSON Backup** and **Import** to transfer data between devices. Treat exported backup files as sensitive because they contain profile and progress information.
- Optional GitHub Gist sync sends the app data to GitHub. A private Gist is **not end-to-end encrypted**; GitHub stores the data and anyone with access to the GitHub account can read it. The token is held only in the current browser tab and is not persisted across reloads. Do not put tokens in URLs or share them.
- The in-app publisher uses a separate fine-grained GitHub token. Restrict it to this repository and grant only **Contents: read and write**. The app publisher does not need an account-wide classic `repo` token.
- Credential-bearing pairing links and data-in-URL snapshot links are disabled. Secure live sharing between two different people's accounts requires a private backend with separate authentication; GitHub Pages alone does not provide that.

## Project status

The page has passed an HTML-boundary check and JavaScript syntax parsing, and the hosted URL has been checked for HTTP reachability. This is not a full automated browser interaction test or a security/medical audit. Review the flows in a browser before relying on them for important health or training decisions.
