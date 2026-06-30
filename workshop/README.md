# Workshop Documentation

This folder contains the MkDocs documentation for the Foundry IQ + Fabric IQ Workshop.

## Local Development

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Serve Locally

```bash
mkdocs serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) to preview.

### Build Static Site

```bash
mkdocs build
```

Output is in the `site/` folder.

## Deploy to GitHub Pages

```bash
mkdocs gh-deploy
```

This builds the site and pushes to the `gh-pages` branch.

## Structure

```
workshop/
├── mkdocs.yml              # MkDocs configuration
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── docs/
    ├── index.md           # Overview
    ├── get-started.md     # Prerequisites & PoC journey
    ├── 01-deploy/         # Deploy Solution
    │   ├── index.md
    │   ├── infrastructure.md
    │   ├── configure.md
    │   └── run.md
    ├── 02-customize/      # Customize for Your Customer
    │   ├── index.md
    │   ├── choose.md
    │   ├── generate.md
    │   └── demo.md
    ├── 03-understand/     # Understand the Technology
    │   ├── index.md
    │   ├── foundry-iq.md
    │   └── fabric-iq.md
    └── 04-cleanup.md      # Cleanup & Next Steps
```
