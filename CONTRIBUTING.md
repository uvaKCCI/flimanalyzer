# Contributing to FLIMAnalyzer

Thank you for helping to improve FLIMAnalyzer.

## Reporting a bug or asking for a feature

Open an [issue](https://github.com/uvaKCCI/flimanalyzer/issues). For a bug, say which
version you use (`Help` → `About FLIMAnalyzer`), your
operating system, what you did, what you expected and what happened. Attach the log
file and, if you can, a small data file that shows the problem.

## Before you open a pull request

- **Ask on the issue first.** Say what you would like to change and wait for a
  maintainer's answer. If there is no issue yet, open one.
- **Issues assigned to a maintainer are already being fixed.** Please don't open pull
  requests for them. The fix is usually in a linked pull request into `dev`, and the
  issue stays open until the release with the fix is published.
- **Pull requests go into `dev`,** not `main`. `main` only receives releases.

Pull requests that fix an issue already being fixed, or that target `main`, are closed.

## Making a change

1. Fork the repository and start a branch from `dev`.
2. Set up the development environment and run the tests as described under
   [Development](README.md#development) in the README.
3. Add a test that fails without your change and passes with it.
4. If the change affects what users see, update the user guide in `docs/userguide`.
5. Open the pull request into `dev`, name the issue it addresses (e.g. `#123`) and
   describe what you changed and why.

All pull requests have to pass the tests in CI before they can be merged.

## License

By contributing, you agree that your contribution is licensed under the
[MIT License](LICENSE) of FLIMAnalyzer.
