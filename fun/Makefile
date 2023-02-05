CC=gcc
CFLAGS=-g -O -static -fno-pie -no-pie -mno-red-zone -nostdlib -nostdinc
CPPFLAGS=-include cosmopolitan.h -I.
LDFLAGS=-Wl,--oformat=binary -Wl,--gc-sections -Wl,-z,max-page-size=0x1000 -fuse-ld=bfd -gdwarf-4 -Wl,-T,ape.lds
LDLIBS=cosmopolitan.a

.PHONY: all
all: 4th.com

%.com : %.com.dbg
	objcopy -S -O binary $< $@

%.com.dbg : %.c crt.o ape-no-modify-self.o ape.lds
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(CPPFLAGS) $(call allbutlast, $^) $(LDLIBS)

crt.o ape-no-modify-self.o ape.lds &: cosmopolitan-amalgamation-2.2.zip
	unzip -u $<

cosmopolitan-amalgamation-2.2.zip :
	wget https://justine.lol/cosmopolitan/cosmopolitan-amalgamation-2.2.zip

clean :
	rm -f *.o ape.lds *.a cosmopolitan-amalgamation-2.2.zip cosmopolitan.h

define allbutlast
$(wordlist 2, $(words $(1)), x $(1))
endef