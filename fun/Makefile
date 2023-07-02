CC = gcc
EC ?= emcc
CFLAGS ?= -Wall -Wextra -O3 -nostartfiles
ARFLAGS ?= -S -fverbose-asm
EFLAGS = -g -gsource-map --source-map-base http://localhost:8000/ -O -Wall -Wextra -fblocks -sEXIT_RUNTIME=0 -sFORCE_FILESYSTEM=1 -sASSERTIONS=1
CPPFLAGS = -include cosmopolitan.h -I.
LDFLAGS = -Wl,--oformat=binary -Wl,--gc-sections -Wl,-z,max-page-size=0x1000 -fuse-ld=bfd -gdwarf-4 -Wl,-T,ape.lds
LDLIBS = cosmopolitan.a

.PHONY: all
all: 4th.com 4th 4th.ll serve

run: 4th
	cat 4th.fs - | ./4th

%.com : %.com.dbg
	objcopy -S -O binary $< $@

%.com.dbg : %.c crt.o ape-no-modify-self.o ape.lds
	$(CC) -g -Os -static -nostdlib -nostdinc -fno-pie -no-pie -mno-red-zone -fno-omit-frame-pointer -pg -mnop-mcount -mno-tls-direct-seg-refs $(LDFLAGS) -o $@ $(CPPFLAGS) $(call allbutlast, $^) $(LDLIBS)

%.wasm : %.c
	$(EC) $(EFLAGS) -o $@ $^

%.js : %.c
	$(EC) $(EFLAGS) -o $@ $^

% : %.c
	$(CC) $(CFLAGS) -mstackrealign -o $@ $^

%.32 : %.c
	$(CC) $(CFLAGS) -ggdb -m32 -o $@ $^

%.s : %.c
	$(CC) $(CFLAGS) $(ARFLAGS) -o $@ $^

%.ll : %.c
	clang $(CFLAGS) -fblocks -lBlocksRuntime -o $@ $^

serve: 4th.js
	open http://localhost:8000/4th.html
	python -m http.server

crt.o ape-no-modify-self.o ape.lds &: cosmopolitan-amalgamation-2.2.zip
	unzip -u $<

cosmopolitan-amalgamation-2.2.zip :
	wget https://justine.lol/cosmopolitan/cosmopolitan-amalgamation-2.2.zip

c4th : 4th.c
	$(CC) -Wall -Wextra --coverage -mstackrealign -o $@ $^

clean :
	$(RM) *.o ape.lds *.a cosmopolitan-amalgamation-2.2.zip cosmopolitan.h 4th.com 4th.com.dbg 4th 4th.ll 4th.wasm 4th.wasm.map 4th.js 4th.32 c4th *.gcda *.gcno

define allbutlast
$(wordlist 2, $(words $(1)), x $(1))
endef
