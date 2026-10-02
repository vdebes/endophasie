# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/vdebes/endophasie/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name          |    Stmts |     Miss |   Cover |   Missing |
|-------------- | -------: | -------: | ------: | --------: |
| client.py     |       29 |       22 |     24% |21-39, 43-47 |
| server.py     |       40 |       27 |     32% | 35-61, 65 |
| streamer.py   |      199 |      103 |     48% |62, 70-71, 76-84, 90, 111-113, 155, 170, 185-186, 190-191, 196-286, 290 |
| transcribe.py |       32 |       15 |     53% |23-29, 49-60, 64-68, 72 |
| **TOTAL**     |  **300** |  **167** | **44%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/vdebes/endophasie/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/vdebes/endophasie/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/vdebes/endophasie/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/vdebes/endophasie/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fvdebes%2Fendophasie%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/vdebes/endophasie/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.