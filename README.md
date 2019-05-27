# gstreamer-example

This repo was created to reproduce an issue: https://gitlab.freedesktop.org/gstreamer/gst-plugins-bad/issues/973

## To Test 1.14.4

- change Dockerfile to use `FROM keepingitneil/gstreamer-1.14.1`. Sorry for the typo, should have named it 1.14.4 which is the actual version being used.
- change integration_tests/Dockerfile to use `FROM keepingitneil/gstreamer-1.14.1`.
- `sudo docker-compose build && sudo docker-compose up`
- logs `WOAH pad added` when a client pad gets added

## To Test 1.16.0

- same as above but with `1.16.0`
