CC = emcc
CFLAGS = -g -gsource-map --source-map-base http://localhost:8000/ -O -Wall -Wextra -fblocks -sEXIT_RUNTIME=0 -sFORCE_FILESYSTEM=1 -sASSERTIONS=1
objects = coi-serviceworker.js TinyBasic.js

.PHONY: all
all: serve

serve: $(objects)
	python -m http.server &
	open http://localhost:8000/

%.js : %.c
	$(CC) $(CFLAGS) -o $@ $^

TinyBasic.c:
	wget http://www.ittybittycomputers.com/IttyBitty/TinyBasic/TinyBasic.c

coi-serviceworker.js:
	npm i --save coi-serviceworker.js
	cp node_modules/coi-serviceworker/coi-serviceworker.js .

clean :
	$(RM) $(objects) TinyBasic.wasm TinyBasic.wasm.map TBout.txt TinyBasic.c