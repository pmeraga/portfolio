# Square Kettle Backtester - Developer Documentation

## Prerequisite:
- Read and Follow [this README](README.md)
- Explore the [quickstart notebook](examples\example-01-importing-data-and-using-the-backtester\quickstart.ipynb)
    - Following this will help you set up your dev environment for the Backtester and make sure that it's working.

## Prerequisite for Frontend Dev
- If you're making changes to the viz (frontend / visualizer), you need to set up Node.js, `npm`.

**Run the React dev server:**

```bash
cd src/viz/frontend
npm install
npm run dev         # launches Vite on http://localhost:3000
```

**Build the frontend (for Python to serve built assets):**

```bash
cd src/viz/frontend
npm run build       # outputs to ../static/dist
```

After build, the Python visualizer can serve the built files directly when you run your backend.

## Making Changes
Every time you make a change, you need to:
- Make sure that the documentation in the [examples folder](examples/) stay up to date. For example, if you added a new feature, add it to the examples folder. Either create a new notebook or add to an existing one. If you made a change to an existing feature, make sure that the examples reflect those changes correctly.
- Write unit tests to test your new code. Add those tests to the [unit_test folder](unit_test/).
