# << project_name >>

## Setting up a development environment

It's recommended to use [uv](https://docs.astral.sh/uv/) to run the project.
[Install uv](https://docs.astral.sh/uv/getting-started/installation/) with:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then run the project with:

```bash
uv run python manage.py runserver
```

Alternatiely, you can sync your environment with:

```bash
uv sync
```

And activate the virtual environment with:

```bash
source .venv/bin/activate
```

From there, you can run commands normally:

```bash
python manage.py runserver
```

## Front end

The front end files can be found in the `assets` folder.
The front end is built with [Vite](https://vitejs.dev/) and [Tailwind CSS](https://tailwindcss.com/).

To build the front end, first install the dependencies:

```bash
cd assets
npm install
```

Then run:

```bash
npm run watch
```

This will build the css files and copy them into your Django static files directory at `/static/dist/`.
