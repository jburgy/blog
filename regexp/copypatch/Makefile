# Stencils are always compiled as freestanding ELF objects, whatever the host
# is: ELF has relocation types for absolute immediates on every ISA, Mach-O
# arm64 does not.  The generated stencils_<arch>.h files are committed, so
# building copypatch.c needs only a C compiler; clang and python3 are for
# regenerating them.
CLANG ?= clang
ARCHS = aarch64 x86_64
STRICT = @../../strict.flags

STENCIL_FLAGS = -std=c2x -O2 -Wall -Wextra -Werror -ffreestanding -fno-pic \
	-mcmodel=large -fno-asynchronous-unwind-tables -fno-stack-protector \
	-fno-jump-tables -ffunction-sections
aarch64_FLAGS = -mbranch-protection=none
x86_64_FLAGS = -fcf-protection=none

all: $(ARCHS:%=stencils_%.h)

stencils_%.h: stencils.c state.h gen.py
	$(CLANG) --target=$*-linux-gnu $(STENCIL_FLAGS) $($*_FLAGS) -c -o $@.o stencils.c
	python3 gen.py $@.o $* > $@
	rm $@.o

# Regenerate unconditionally, then fail if the committed headers differ: make's
# timestamp check can miss an edit, and a stale header would be tested as if current.
# Output depends on the clang version, so run this where the headers were made.
# macOS can run the x86-64 build under Rosetta; elsewhere only the host ISA runs
check:
	$(MAKE) -B all
	git diff --exit-code -- $(ARCHS:%=stencils_%.h)
	$(CC) $(STRICT) -o copypatch copypatch.c && ./copypatch > /dev/null
	@if [ "$$(uname)" = Darwin ]; then \
		$(CC) $(STRICT) -arch x86_64 -o copypatch.x86_64 copypatch.c && \
		arch -x86_64 ./copypatch.x86_64 > /dev/null; \
	fi

clean:
	rm -f copypatch copypatch.x86_64 *.o

.PHONY: all check clean
