#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/syscall.h>

static int rodata[] = {
    /* STATE      */ [5120] =    0,
    /* HERE       */ [5121] = 5559 << 2,
    /* LATEST     */ [5122] = 5554 << 2,
    /* S0         */ [5123] = 2048 << 2,
    /* BASE       */ [5124] =   10,
    /* DROP       */ [5133] =    0 << 2, [5134] = 0x4f524404, [5135] = 0x00000050, [5136] = 1,
    /* SWAP       */ [5137] = 5133 << 2, [5138] = 0x41575304, [5139] = 0x00000050, [5140] = 2,
    /* DUP        */ [5141] = 5137 << 2, [5142] = 0x50554403, [5143] = 3,
    /* OVER       */ [5144] = 5141 << 2, [5145] = 0x45564f04, [5146] = 0x00000052, [5147] = 4,
    /* ROT        */ [5148] = 5144 << 2, [5149] = 0x544f5203, [5150] = 5,
    /* -ROT       */ [5151] = 5148 << 2, [5152] = 0x4f522d04, [5153] = 0x00000054, [5154] = 6,
    /* 2DROP      */ [5155] = 5151 << 2, [5156] = 0x52443205, [5157] = 0x0000504f, [5158] = 7,
    /* 2DUP       */ [5159] = 5155 << 2, [5160] = 0x55443204, [5161] = 0x00000050, [5162] = 8,
    /* 2SWAP      */ [5163] = 5159 << 2, [5164] = 0x57533205, [5165] = 0x00005041, [5166] = 9,
    /* ?DUP       */ [5167] = 5163 << 2, [5168] = 0x55443f04, [5169] = 0x00000050, [5170] = 10,
    /* 1+         */ [5171] = 5167 << 2, [5172] = 0x002b3102, [5173] = 11,
    /* 1-         */ [5174] = 5171 << 2, [5175] = 0x002d3102, [5176] = 12,
    /* 4+         */ [5177] = 5174 << 2, [5178] = 0x002b3402, [5179] = 13,
    /* 4-         */ [5180] = 5177 << 2, [5181] = 0x002d3402, [5182] = 14,
    /* +          */ [5183] = 5180 << 2, [5184] = 0x00002b01, [5185] = 15,
    /* -          */ [5186] = 5183 << 2, [5187] = 0x00002d01, [5188] = 16,
    /* *          */ [5189] = 5186 << 2, [5190] = 0x00002a01, [5191] = 17,
    /* /MOD       */ [5192] = 5189 << 2, [5193] = 0x4f4d2f04, [5194] = 0x00000044, [5195] = 18,
    /* =          */ [5196] = 5192 << 2, [5197] = 0x00003d01, [5198] = 19,
    /* <>         */ [5199] = 5196 << 2, [5200] = 0x003e3c02, [5201] = 20,
    /* <          */ [5202] = 5199 << 2, [5203] = 0x00003c01, [5204] = 21,
    /* >          */ [5205] = 5202 << 2, [5206] = 0x00003e01, [5207] = 22,
    /* <=         */ [5208] = 5205 << 2, [5209] = 0x003d3c02, [5210] = 23,
    /* >=         */ [5211] = 5208 << 2, [5212] = 0x003d3e02, [5213] = 24,
    /* 0=         */ [5214] = 5211 << 2, [5215] = 0x003d3002, [5216] = 25,
    /* 0<>        */ [5217] = 5214 << 2, [5218] = 0x3e3c3003, [5219] = 26,
    /* 0<         */ [5220] = 5217 << 2, [5221] = 0x003c3002, [5222] = 27,
    /* 0>         */ [5223] = 5220 << 2, [5224] = 0x003e3002, [5225] = 28,
    /* 0<=        */ [5226] = 5223 << 2, [5227] = 0x3d3c3003, [5228] = 29,
    /* 0>=        */ [5229] = 5226 << 2, [5230] = 0x3d3e3003, [5231] = 30,
    /* AND        */ [5232] = 5229 << 2, [5233] = 0x444e4103, [5234] = 31,
    /* OR         */ [5235] = 5232 << 2, [5236] = 0x00524f02, [5237] = 32,
    /* XOR        */ [5238] = 5235 << 2, [5239] = 0x524f5803, [5240] = 33,
    /* INVERT     */ [5241] = 5238 << 2, [5242] = 0x564e4906, [5243] = 0x00545245, [5244] = 34,
    /* EXIT       */ [5245] = 5241 << 2, [5246] = 0x49584504, [5247] = 0x00000054, [5248] = 35,
    /* LIT        */ [5249] = 5245 << 2, [5250] = 0x54494c03, [5251] = 36,
    /* !          */ [5252] = 5249 << 2, [5253] = 0x00002101, [5254] = 37,
    /* @          */ [5255] = 5252 << 2, [5256] = 0x00004001, [5257] = 38,
    /* +!         */ [5258] = 5255 << 2, [5259] = 0x00212b02, [5260] = 39,
    /* -!         */ [5261] = 5258 << 2, [5262] = 0x00212d02, [5263] = 40,
    /* C!         */ [5264] = 5261 << 2, [5265] = 0x00214302, [5266] = 41,
    /* C@         */ [5267] = 5264 << 2, [5268] = 0x00404302, [5269] = 42,
    /* C@C!       */ [5270] = 5267 << 2, [5271] = 0x43404304, [5272] = 0x00000021, [5273] = 43,
    /* CMOVE      */ [5274] = 5270 << 2, [5275] = 0x4f4d4305, [5276] = 0x00004556, [5277] = 44,
    /* STATE      */ [5278] = 5274 << 2, [5279] = 0x41545305, [5280] = 0x00004554, [5281] = 45,
    /* HERE       */ [5282] = 5278 << 2, [5283] = 0x52454804, [5284] = 0x00000045, [5285] = 46,
    /* LATEST     */ [5286] = 5282 << 2, [5287] = 0x54414c06, [5288] = 0x00545345, [5289] = 47,
    /* S0         */ [5290] = 5286 << 2, [5291] = 0x00305302, [5292] = 48,
    /* BASE       */ [5293] = 5290 << 2, [5294] = 0x53414204, [5295] = 0x00000045, [5296] = 49,
    /* VERSION    */ [5297] = 5293 << 2, [5298] = 0x52455607, [5299] = 0x4e4f4953, [5300] = 50,
    /* R0         */ [5301] = 5297 << 2, [5302] = 0x00305202, [5303] = 51,
    /* DOCOL      */ [5304] = 5301 << 2, [5305] = 0x434f4405, [5306] = 0x00004c4f, [5307] = 52,
    /* F_IMMED    */ [5308] = 5304 << 2, [5309] = 0x495f4607, [5310] = 0x44454d4d, [5311] = 53,
    /* F_HIDDEN   */ [5312] = 5308 << 2, [5313] = 0x485f4608, [5314] = 0x45444449, [5315] = 0x0000004e, [5316] = 54,
    /* F_LENMASK  */ [5317] = 5312 << 2, [5318] = 0x4c5f4609, [5319] = 0x414d4e45, [5320] = 0x00004b53, [5321] = 55,
    /* SYS_EXIT   */ [5322] = 5317 << 2, [5323] = 0x53595308, [5324] = 0x4958455f, [5325] = 0x00000054, [5326] = 56,
    /* SYS_OPEN   */ [5327] = 5322 << 2, [5328] = 0x53595308, [5329] = 0x45504f5f, [5330] = 0x0000004e, [5331] = 57,
    /* SYS_CLOSE  */ [5332] = 5327 << 2, [5333] = 0x53595309, [5334] = 0x4f4c435f, [5335] = 0x00004553, [5336] = 58,
    /* SYS_READ   */ [5337] = 5332 << 2, [5338] = 0x53595308, [5339] = 0x4145525f, [5340] = 0x00000044, [5341] = 59,
    /* SYS_WRITE  */ [5342] = 5337 << 2, [5343] = 0x53595309, [5344] = 0x4952575f, [5345] = 0x00004554, [5346] = 60,
    /* SYS_CREAT  */ [5347] = 5342 << 2, [5348] = 0x53595309, [5349] = 0x4552435f, [5350] = 0x00005441, [5351] = 61,
    /* SYS_BRK    */ [5352] = 5347 << 2, [5353] = 0x53595307, [5354] = 0x4b52425f, [5355] = 62,
    /* O_RDONLY   */ [5356] = 5352 << 2, [5357] = 0x525f4f08, [5358] = 0x4c4e4f44, [5359] = 0x00000059, [5360] = 63,
    /* O_WRONLY   */ [5361] = 5356 << 2, [5362] = 0x575f4f08, [5363] = 0x4c4e4f52, [5364] = 0x00000059, [5365] = 64,
    /* O_RDWR     */ [5366] = 5361 << 2, [5367] = 0x525f4f06, [5368] = 0x00525744, [5369] = 65,
    /* O_CREAT    */ [5370] = 5366 << 2, [5371] = 0x435f4f07, [5372] = 0x54414552, [5373] = 66,
    /* O_EXCL     */ [5374] = 5370 << 2, [5375] = 0x455f4f06, [5376] = 0x004c4358, [5377] = 67,
    /* O_TRUNC    */ [5378] = 5374 << 2, [5379] = 0x545f4f07, [5380] = 0x434e5552, [5381] = 68,
    /* O_APPEND   */ [5382] = 5378 << 2, [5383] = 0x415f4f08, [5384] = 0x4e455050, [5385] = 0x00000044, [5386] = 69,
    /* O_NONBLOCK */ [5387] = 5382 << 2, [5388] = 0x4e5f4f0a, [5389] = 0x4c424e4f, [5390] = 0x004b434f, [5391] = 70,
    /* >R         */ [5392] = 5387 << 2, [5393] = 0x00523e02, [5394] = 71,
    /* R>         */ [5395] = 5392 << 2, [5396] = 0x003e5202, [5397] = 72,
    /* RSP@       */ [5398] = 5395 << 2, [5399] = 0x50535204, [5400] = 0x00000040, [5401] = 73,
    /* RSP!       */ [5402] = 5398 << 2, [5403] = 0x50535204, [5404] = 0x00000021, [5405] = 74,
    /* RDROP      */ [5406] = 5402 << 2, [5407] = 0x52445205, [5408] = 0x0000504f, [5409] = 75,
    /* DSP@       */ [5410] = 5406 << 2, [5411] = 0x50534404, [5412] = 0x00000040, [5413] = 76,
    /* DSP!       */ [5414] = 5410 << 2, [5415] = 0x50534404, [5416] = 0x00000021, [5417] = 77,
    /* KEY        */ [5418] = 5414 << 2, [5419] = 0x59454b03, [5420] = 78,
    /* EMIT       */ [5421] = 5418 << 2, [5422] = 0x494d4504, [5423] = 0x00000054, [5424] = 79,
    /* WORD       */ [5425] = 5421 << 2, [5426] = 0x524f5704, [5427] = 0x00000044, [5428] = 80,
    /* NUMBER     */ [5429] = 5425 << 2, [5430] = 0x4d554e06, [5431] = 0x00524542, [5432] = 81,
    /* FIND       */ [5433] = 5429 << 2, [5434] = 0x4e494604, [5435] = 0x00000044, [5436] = 82,
    /* >CFA       */ [5437] = 5433 << 2, [5438] = 0x46433e04, [5439] = 0x00000041, [5440] = 83,
    /* >DFA       */ [5441] = 5437 << 2, [5442] = 0x46443e04, [5443] = 0x00000041, [5444] = 0, [5445] = 5440 << 2, [5446] = 5179 << 2, [5447] = 5248 << 2,
    /* CREATE     */ [5448] = 5441 << 2, [5449] = 0x45524306, [5450] = 0x00455441, [5451] = 84,
    /* ,          */ [5452] = 5448 << 2, [5453] = 0x00002c01, [5454] = 85,
    /* [          */ [5455] = 5452 << 2, [5456] = 0x00005b81, [5457] = 86,
    /* ]          */ [5458] = 5455 << 2, [5459] = 0x00005d01, [5460] = 87,
    /* IMMEDIATE  */ [5461] = 5458 << 2, [5462] = 0x4d4d4989, [5463] = 0x41494445, [5464] = 0x00004554, [5465] = 88,
    /* HIDDEN     */ [5466] = 5461 << 2, [5467] = 0x44494806, [5468] = 0x004e4544, [5469] = 89,
    /* HIDE       */ [5470] = 5466 << 2, [5471] = 0x44494804, [5472] = 0x00000045, [5473] = 0, [5474] = 5428 << 2, [5475] = 5436 << 2, [5476] = 5469 << 2, [5477] = 5248 << 2,
    /* :          */ [5478] = 5470 << 2, [5479] = 0x00003a01, [5480] = 0, [5481] = 5428 << 2, [5482] = 5451 << 2, [5483] = 5251 << 2, [5484] = 0, [5485] = 5454 << 2, [5486] = 5289 << 2, [5487] = 5257 << 2, [5488] = 5469 << 2, [5489] = 5460 << 2, [5490] = 5248 << 2,
    /* ;          */ [5491] = 5478 << 2, [5492] = 0x00003b81, [5493] = 0, [5494] = 5251 << 2, [5495] = 5248 << 2, [5496] = 5454 << 2, [5497] = 5289 << 2, [5498] = 5257 << 2, [5499] = 5469 << 2, [5500] = 5457 << 2, [5501] = 5248 << 2,
    /* '          */ [5502] = 5491 << 2, [5503] = 0x00002701, [5504] = 90,
    /* BRANCH     */ [5505] = 5502 << 2, [5506] = 0x41524206, [5507] = 0x0048434e, [5508] = 91,
    /* 0BRANCH    */ [5509] = 5505 << 2, [5510] = 0x52423007, [5511] = 0x48434e41, [5512] = 92,
    /* LITSTRING  */ [5513] = 5509 << 2, [5514] = 0x54494c09, [5515] = 0x49525453, [5516] = 0x0000474e, [5517] = 93,
    /* TELL       */ [5518] = 5513 << 2, [5519] = 0x4c455404, [5520] = 0x0000004c, [5521] = 94,
    /* INTERPRET  */ [5522] = 5518 << 2, [5523] = 0x544e4909, [5524] = 0x52505245, [5525] = 0x00005445, [5526] = 95,
    /* QUIT       */ [5527] = 5522 << 2, [5528] = 0x49555104, [5529] = 0x00000054, [5530] = 0, [5531] = 5303 << 2, [5532] = 5405 << 2, [5533] = 5526 << 2, [5534] = 5508 << 2, [5535] = -8,
    /* CHAR       */ [5536] = 5527 << 2, [5537] = 0x41484304, [5538] = 0x00000052, [5539] = 96,
    /* EXECUTE    */ [5540] = 5536 << 2, [5541] = 0x45584507, [5542] = 0x45545543, [5543] = 97,
    /* SYSCALL3   */ [5544] = 5540 << 2, [5545] = 0x53595308, [5546] = 0x4c4c4143, [5547] = 0x00000033, [5548] = 98,
    /* SYSCALL2   */ [5549] = 5544 << 2, [5550] = 0x53595308, [5551] = 0x4c4c4143, [5552] = 0x00000032, [5553] = 99,
    /* SYSCALL1   */ [5554] = 5549 << 2, [5555] = 0x53595308, [5556] = 0x4c4c4143, [5557] = 0x00000031, [5558] = 100,
};
static int *memory;
static char *bytes;

char key(void) {
    static int currkey = 0x4000, buftop = 0x4000;
    ssize_t c;

    while (buftop <= currkey) {
        currkey = 0x4000;
        c = read(STDIN_FILENO, bytes + currkey, 0x1000);
        if (c < 0) {
            char *s = strerror(errno);
            write(STDERR_FILENO, s, strlen(s));
            exit(EIO);
        }
        buftop = 0x4000 + c;
    }
    return bytes[currkey++];
}

int word(void) {
    char ch, *s = bytes + 0x5014;

    do
    {
        ch = key();
        if (ch == '\\') /* comment ⇒ skip line */
            do
                ch = key();
            while (ch != '\n');
    } while (ch <= ' ');

    do
    {
        *s++ = ch;
        ch = key();
    } while (ch > ' ');

    return s - (bytes + 0x5014);
}

int find(int count, int name) {
    int word = memory[0x1402]; /* LATEST */

    while (word && (((bytes[word + 4] & 0x3F) != count) || memcmp(bytes + word + 5, bytes + name, (unsigned)count)))
        word = memory[word >> 2];

    return word;
}

struct num_t {
    int result;
    int remaining;
};

struct num_t number(int n, int s) {
    int digit, res = 0, sign = 1, base = memory[0x1404];

    switch (bytes[s]) {
        case '-':
            sign = -1;
            [[fallthrough]];
        case '+':
            --n;
            ++s;
            break;
    }

    do {
        res *= base;
        digit = bytes[s++] - '0';
        if (digit < 0)
            break;
        if (digit > 9) {
            digit -= 7; /* 'A' - '0' - 10*/
            if (digit < 10)
                break;
        }
        if (digit >= base)
            break;
        res += digit;
    } while (--n);

    return (struct num_t) { .result = res * sign, .remaining = n };
}

int code_field_address(int word) {
    word += 4;
    word += (bytes[word] & 0x1F) + 4;
    word &= ~3;
    return word;
}

void *set_up_data_segment(const void *src, size_t n) {
    void *here = sbrk(0x10000);
    if (here == (void *)-1)
        exit(errno);

    return memcpy((void *)here, src, n);
}

int main(void) {
    register int sp = 0x0800;
    register int rsp = 0x1000;
    register int cfa = 5530, ip = 0;
    register int a, b, c, d;
    struct num_t num;

    memory = (int *)set_up_data_segment(rodata, sizeof rodata);
    bytes = (char *)memory;

    while (1) {
        switch (memory[cfa]) {
            case 0: /* DOCOL */
                memory[--rsp] = ip;
                ip = cfa + 1;
                break;
            case 1: /* DROP */
                ++sp;
                break;
            case 2: /* SWAP */
                a = memory[sp + 1];
                memory[sp + 1] = memory[sp];
                memory[sp] = a;
                break;
            case 3: /* DUP */
                --sp;
                memory[sp] = memory[sp + 1];
                break;
            case 4: /* OVER */
                --sp;
                memory[sp] = memory[sp + 2];
                break;
            case 5: /* ROT */
                a = memory[sp + 0];
                b = memory[sp + 1];
                c = memory[sp + 2];
                memory[sp + 2] = b;
                memory[sp + 1] = a;
                memory[sp + 0] = c;
                break;
            case 6: /* -ROT */
                a = memory[sp + 0];
                b = memory[sp + 1];
                c = memory[sp + 2];
                memory[sp + 2] = a;
                memory[sp + 1] = c;
                memory[sp + 0] = b;
                break;
            case 7: /* 2DROP */
                sp += 2;
                break;
            case 8: /* 2DUP */
                sp -= 2;
                memory[sp + 0] = memory[sp + 2];
                memory[sp + 1] = memory[sp + 3];
                break;
            case 9: /* 2SWAP */
                a = memory[sp + 0];
                b = memory[sp + 1];
                c = memory[sp + 2];
                d = memory[sp + 3];
                memory[sp + 3] = b;
                memory[sp + 2] = a;
                memory[sp + 1] = d;
                memory[sp + 0] = c;
                break;
            case 10: /* ?DUP */
                a = memory[sp];
                if (a)
                    memory[--sp] = a;
                break;
            case 11: /* 1+ */
                ++memory[sp];
                break;
            case 12: /* 1- */
                --memory[sp];
                break;
            case 13: /* 4+ */
                memory[sp] += 4;
                break;
            case 14: /* 4- */
                memory[sp] -= 4;
                break;
            case 15: /* + */
                memory[sp + 1] += memory[sp];
                ++sp;
                break;
            case 16: /* - */
                memory[sp + 1] -= memory[sp];
                ++sp;
                break;
            case 17: /* * */
                memory[sp + 1] *= memory[sp];
                ++sp;
                break;
            case 18: /* /MOD */
                a = memory[sp + 1];
                b = memory[sp + 0];
                memory[sp + 1] = a % b;
                memory[sp + 0] = a / b;
                break;
            case 19: /* = */
                memory[sp + 1] = memory[sp + 1] == memory[sp];
                ++sp;
                break;
            case 20: /* <> */
                memory[sp + 1] = memory[sp + 1] != memory[sp];
                ++sp;
                break;
            case 21: /* < */
                memory[sp + 1] = memory[sp + 1] < memory[sp];
                ++sp;
                break;
            case 22: /* > */
                memory[sp + 1] = memory[sp + 1] > memory[sp];
                ++sp;
                break;
            case 23: /* <= */
                memory[sp + 1] = memory[sp + 1] <= memory[sp];
                ++sp;
                break;
            case 24: /* >= */
                memory[sp + 1] = memory[sp + 1] >= memory[sp];
                ++sp;
                break;
            case 25: /* 0= */
                memory[sp] = !memory[sp];
                break;
            case 26: /* 0<> */
                memory[sp] = memory[sp] != 0;
                break;
            case 27: /* 0< */
                memory[sp] = memory[sp] < 0;
                break;
            case 28: /* 0> */
                memory[sp] = memory[sp] > 0;
                break;
            case 29: /* 0<= */
                memory[sp] = memory[sp] <= 0;
                break;
            case 30: /* 0>= */
                memory[sp] = memory[sp] >= 0;
                break;
            case 31: /* AND */
                memory[sp + 1] &= memory[sp];
                ++sp;
                break;
            case 32: /* OR */
                memory[sp + 1] |= memory[sp];
                ++sp;
                break;
            case 33: /* XOR */
                memory[sp + 1] ^= memory[sp];
                ++sp;
                break;
            case 34: /* INVERT */
                memory[sp] = ~memory[sp];
                break;
            case 35: /* EXIT */
                ip = memory[rsp++];
                break;
            case 36: /* LIT */
                memory[--sp] = memory[ip++];
                break;
            case 37: /* ! */
                memory[memory[sp] >> 2] = memory[sp + 1];
                sp += 2;
                break;
            case 38: /* @ */
                memory[sp] = memory[memory[sp] >> 2];
                break;
            case 39: /* +! */
                memory[memory[sp] >> 2] += memory[sp + 1];
                sp += 2;
                break;
            case 40: /* -! */
                memory[memory[sp] >> 2] -= memory[sp + 1];
                sp += 2;
                break;
            case 41: /* C! */
                bytes[memory[sp]] = (char)memory[sp + 1];
                sp += 2;
                break;
            case 42: /* C@ */
                memory[sp] = bytes[memory[sp]];
                break;
            case 43: /* C@C! */
                bytes[memory[sp + 1]] = bytes[memory[sp]];
                ++sp;
                break;
            case 44: /* CMOVE */
                (void)memmove(bytes + memory[sp + 1], bytes + memory[sp + 2], (size_t)memory[sp]);
                sp += 2;
                break;
            case 45: /* STATE */
                memory[--sp] = 0x1400 << 2;
                break;
            case 46: /* HERE */
                memory[--sp] = 0x1401 << 2;
                break;
            case 47: /* LATEST */
                memory[--sp] = 0x1402 << 2;
                break;
            case 48: /* S0 */
                memory[--sp] = 0x1403 << 2;
                break;
            case 49: /* BASE */
                memory[--sp] = 0x1404 << 2;
                break;
            case 50: /* VERSION */
                memory[--sp] = 47;
                break;
            case 51: /* R0 */
                memory[--sp] = 0x1000 << 2;
                break;
            case 52: /* DOCOL */
                memory[--sp] = 0;
                break;
            case 53: /* F_IMMED */
                memory[--sp] = 0x80;
                break;
            case 54: /* F_HIDDEN */
                memory[--sp] = 0x20;
                break;
            case 55: /* F_LENMASK */
                memory[--sp] = 0x1F;
                break;
            case 56: /* SYS_EXIT */
                memory[--sp] = SYS_exit;
                break;
            case 57: /* SYS_OPEN */
                memory[--sp] = SYS_open;
                break;
            case 58: /* SYS_CLOSE */
                memory[--sp] = SYS_close;
                break;
            case 59: /* SYS_READ */
                memory[--sp] = SYS_read;
                break;
            case 60: /* SYS_WRITE */
                memory[--sp] = SYS_write;
                break;
            case 61: /* SYS_CREAT */
                memory[--sp] = SYS_creat;
                break;
            case 62: /* SYS_BRK */
                memory[--sp] = SYS_brk;
                break;
            case 63: /* O_RDONLY */
                memory[--sp] = O_RDONLY;
                break;
            case 64: /* O_WRONLY */
                memory[--sp] = O_WRONLY;
                break;
            case 65: /* O_RDWR */
                memory[--sp] = O_RDWR;
                break;
            case 66: /* O_CREAT */
                memory[--sp] = O_CREAT;
                break;
            case 67: /* O_EXCL */
                memory[--sp] = O_EXCL;
                break;
            case 68: /* O_TRUNC */
                memory[--sp] = O_TRUNC;
                break;
            case 69: /* O_APPEND */
                memory[--sp] = O_APPEND;
                break;
            case 70: /* O_NONBLOCK */
                memory[--sp] = O_NONBLOCK;
                break;
            case 71: /* >R */
                memory[--rsp] = memory[sp++] >> 2;
                break;
            case 72: /* R> */
                memory[--sp] = memory[rsp++] << 2;
                break;
            case 73: /* RSP@ */
                memory[--sp] = rsp << 2;
                break;
            case 74: /* RSP! */
                rsp = memory[sp++] >> 2;
                break;
            case 75: /* RDROP */
                ++rsp;
                break;
            case 76: /* DSP@ */
                a = sp--;
                memory[sp] = a << 2;
                break;
            case 77: /* DSP! */
                sp = memory[sp] >> 2;
                break;
            case 78: /* KEY */
                memory[--sp] = key();
                break;
            case 79: /* EMIT */
                (void)(write(STDOUT_FILENO, memory + sp++, 1) + 1);
                break;
            case 80: /* WORD */
                memory[--sp] = 0x5014;
                memory[--sp] = word();
                break;
            case 81: /* NUMBER */
                num = number(memory[sp], memory[sp + 1]);
                memory[sp + 1] = num.result;
                memory[sp + 0] = num.remaining;
                break;
            case 82: /* FIND */
                memory[sp + 1] = find(memory[sp], memory[sp + 1]);
                ++sp;
                break;
            case 83: /* >CFA */
                memory[sp] = code_field_address(memory[sp]);
                break;
            case 84: /* CREATE */
                a = memory[0x1401];
                memory[a >> 2] = memory[0x1402];
                bytes[a + 4] = (char)memory[sp];
                memcpy(bytes + a + 5, bytes + memory[sp + 1], (size_t)memory[sp]);
                memory[0x1401] = code_field_address(a);
                memory[0x1402] = a;
                sp += 2;
                break;
            case 85: /* , */
                memory[memory[0x1401] >> 2] = memory[sp++];
                memory[0x1401] += 4;
                break;
            case 86: /* [ */
                memory[0x1400] = 0;
                break;
            case 87: /* ] */
                memory[0x1400] = 1;
                break;
            case 88: /* IMMEDIATE */
                memory[(memory[0x1402] >> 2) + 1] ^= 0x80;
                break;
            case 89: /* HIDDEN */
                memory[(memory[sp++] >> 2) + 1] ^= 0x20;
                break;
            case 90: /* ' */
                memory[--sp] = memory[ip++];
                break;
            case 91: /* BRANCH */
                ip += memory[ip] >> 2;
                break;
            case 92: /* 0BRANCH */
                ip += memory[sp++] ? 1 : memory[ip] >> 2;
                break;
            case 93: /* LITSTRING */
                memory[--sp] = (ip + 1) << 2;
                memory[--sp] = memory[ip];
                ip += 1 + ((memory[ip] + 3) >> 2);
                break;
            case 94: /* TELL */
                (void)(write(STDOUT_FILENO, bytes + memory[sp + 1], (size_t)memory[sp]) + 1);
                sp += 2;
                break;
            case 95: /* INTERPRET */
                a = word();
                b = find(a, 0x5014);
                if (b) {
                    cfa = code_field_address(b);
                    if ((bytes[b + 4] & 0x80) || !memory[0x1400]) {
                        cfa >>= 2;
                        continue;
                    }
                    memory[memory[0x1401] >> 2] = cfa;
                    memory[0x1401] += 4;
                } else {
                    num = number(a, 0x5014);
                    if (num.remaining) {
                        (void)(write(STDERR_FILENO, "PARSE ERROR: ", 13) + 1);
                        (void)(write(STDERR_FILENO, bytes + 0x5014, (size_t)a) + 1);
                        (void)(write(STDERR_FILENO, "\n", 1) + 1);
                    } else if (memory[0x1400]) {
                        memory[memory[0x1401] >> 2] = 5251 << 2; /* LIT */
                        memory[0x1401] += 4;
                        memory[memory[0x1401] >> 2] = num.result;
                        memory[0x1401] += 4;
                    } else {
                        memory[--sp] = num.result;
                    }
                }
                break;
            case 96: /* CHAR */
                word();
                memory[--sp] = bytes[0x5014];
                break;
            case 97: /* EXECUTE */
                cfa = memory[sp++] >> 2;
                continue;
            case 98: /* SYSCALL3 */
                memory[sp + 3] = syscall(memory[sp], memory[sp + 1], memory[sp + 2], memory[sp + 3]);
                sp += 3;
                break;
            case 99: /* SYSCALL2 */
                memory[sp + 2] = syscall(memory[sp], memory[sp + 1], memory[sp + 2]);
                sp += 2;
                break;
            case 100: /* SYSCALL1 */
                memory[sp + 1] = syscall(memory[sp], memory[sp + 1]);
                if (memory[sp] == SYS_brk)
                    memory[sp + 1] -= (int)bytes;
                sp += 1;
                break;
        }
        cfa = memory[ip++] >> 2;
    }
    return cfa;
}