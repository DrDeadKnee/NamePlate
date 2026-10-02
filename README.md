# NamePlates

This repo exists to house code to create 3d images for miniature name plates. 
For any individual name plate, target surface geometry, name, direction, and font can be given.

The software needs to run in batch or individual modes.

The target geometry might be flat, in which case a height and width need to be specified. However, the
traditional target would be a games workshop miniature base. these bases are well described as slices of
a cone - giving something like a beveled cylinder with a broad face and a short height. For example, a typical
"40mm" base is 39mm in diameter at the bottom, 37mm in diameter at the top, and 4.5mm in height. A nameplate
that fits on that base would need to match the curvature almost exactly on the back 
(err on a configuratble tolerance defaulting to 1% "too straight").

Some default parameters are written in configs/default.yml

