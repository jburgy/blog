CC=gcc
ES=emcc
CFLAGS=-g -O -static -fno-pie -no-pie -mno-red-zone -nostdlib -nostdinc
EFLAGS=-g -gsource-map --source-map-base http://localhost:8000/ -O -Wall -Wextra -fblocks -sNO_EXIT_RUNTIME=1 -sFORCE_FILESYSTEM=1 -sASSERTIONS=1
CPPFLAGS=-include cosmopolitan.h -I.
LDFLAGS=-Wl,--oformat=binary -Wl,--gc-sections -Wl,-z,max-page-size=0x1000 -fuse-ld=bfd -gdwarf-4 -Wl,-T,ape.lds
LDLIBS=cosmopolitan.a

.PHONY: all
all: 4th.com

%.com : %.com.dbg
	objcopy -S -O binary $< $@

%.com.dbg : %.c crt.o ape-no-modify-self.o ape.lds
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(CPPFLAGS) $(call allbutlast, $^) $(LDLIBS)

%.wasm : %.c
	$(ES) $(EFLAGS) -o $@ $^

%.js : %.c
	$(ES) $(EFLAGS) -o $@ $^

% : %.c
	$(CC) -Wall -Wextra -O3 -nostartfiles -mpreferred-stack-boundary=3 -o $@ $^

%.s : %.c
	$(CC) -Wall -Wextra -O3 -nostartfiles -mpreferred-stack-boundary=3 -S -fverbose-asm -o $@ $^

%.ll : %.c
	clang -Wall -Wextra -O3 -nostartfiles -fblocks -lBlocksRuntime -o $@ $^

serve: 4th.js
	open http://localhost:8000/4th.html
	python -m http.server

crt.o ape-no-modify-self.o ape.lds &: cosmopolitan-amalgamation-2.2.zip
	unzip -u $<

cosmopolitan-amalgamation-2.2.zip :
	wget https://justine.lol/cosmopolitan/cosmopolitan-amalgamation-2.2.zip

clean :
	rm -f *.o ape.lds *.a cosmopolitan-amalgamation-2.2.zip cosmopolitan.h

define allbutlast
$(wordlist 2, $(words $(1)), x $(1))
endef