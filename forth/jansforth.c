#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/syscall.h>

static int memory[0x8000] = {
    /* STATE      */ [5120] =    0,
    /* HERE       */ [5121] = 5562 << 2,
    /* LATEST     */ [5122] = 5557,
    /* S0         */ [5123] = 2048,
    /* BASE       */ [5124] =   10,
    /* DROP       */ [5133] =    0, [5134] = 0x4f524404, [5135] = 0x00000050, [5136] = 1,
    /* SWAP       */ [5137] = 5133, [5138] = 0x41575304, [5139] = 0x00000050, [5140] = 2,
    /* DUP        */ [5141] = 5137, [5142] = 0x50554403, [5143] = 3,
    /* OVER       */ [5144] = 5141, [5145] = 0x45564f04, [5146] = 0x00000052, [5147] = 4,
    /* ROT        */ [5148] = 5144, [5149] = 0x544f5203, [5150] = 5,
    /* -ROT       */ [5151] = 5148, [5152] = 0x4f522d04, [5153] = 0x00000054, [5154] = 6,
    /* 2DROP      */ [5155] = 5151, [5156] = 0x52443205, [5157] = 0x0000504f, [5158] = 7,
    /* 2DUP       */ [5159] = 5155, [5160] = 0x55443204, [5161] = 0x00000050, [5162] = 8,
    /* 2SWAP      */ [5163] = 5159, [5164] = 0x57533205, [5165] = 0x00005041, [5166] = 9,
    /* ?DUP       */ [5167] = 5163, [5168] = 0x55443f04, [5169] = 0x00000050, [5170] = 10,
    /* 1+         */ [5171] = 5167, [5172] = 0x002b3102, [5173] = 11,
    /* 1-         */ [5174] = 5171, [5175] = 0x002d3102, [5176] = 12,
    /* 4+         */ [5177] = 5174, [5178] = 0x002b3402, [5179] = 13,
    /* 4-         */ [5180] = 5177, [5181] = 0x002d3402, [5182] = 14,
    /* +          */ [5183] = 5180, [5184] = 0x00002b01, [5185] = 15,
    /* -          */ [5186] = 5183, [5187] = 0x00002d01, [5188] = 16,
    /* *          */ [5189] = 5186, [5190] = 0x00002a01, [5191] = 17,
    /* /MOD       */ [5192] = 5189, [5193] = 0x4f4d2f04, [5194] = 0x00000044, [5195] = 18,
    /* =          */ [5196] = 5192, [5197] = 0x00003d01, [5198] = 19,
    /* <>         */ [5199] = 5196, [5200] = 0x003e3c02, [5201] = 20,
    /* <=         */ [5202] = 5199, [5203] = 0x003d3c02, [5204] = 21,
    /* <          */ [5205] = 5202, [5206] = 0x00003c01, [5207] = 22,
    /* >          */ [5208] = 5205, [5209] = 0x00003e01, [5210] = 23,
    /* <=         */ [5211] = 5208, [5212] = 0x003d3c02, [5213] = 24,
    /* >=         */ [5214] = 5211, [5215] = 0x003d3e02, [5216] = 25,
    /* 0=         */ [5217] = 5214, [5218] = 0x003d3002, [5219] = 26,
    /* 0<>        */ [5220] = 5217, [5221] = 0x3e3c3003, [5222] = 27,
    /* 0<         */ [5223] = 5220, [5224] = 0x003c3002, [5225] = 28,
    /* 0>         */ [5226] = 5223, [5227] = 0x003e3002, [5228] = 29,
    /* 0<=        */ [5229] = 5226, [5230] = 0x3d3c3003, [5231] = 30,
    /* 0>=        */ [5232] = 5229, [5233] = 0x3d3e3003, [5234] = 31,
    /* AND        */ [5235] = 5232, [5236] = 0x444e4103, [5237] = 32,
    /* OR         */ [5238] = 5235, [5239] = 0x00524f02, [5240] = 33,
    /* XOR        */ [5241] = 5238, [5242] = 0x524f5803, [5243] = 34,
    /* INVERT     */ [5244] = 5241, [5245] = 0x564e4906, [5246] = 0x00545245, [5247] = 35,
    /* EXIT       */ [5248] = 5244, [5249] = 0x49584504, [5250] = 0x00000054, [5251] = 36,
    /* LIT        */ [5252] = 5248, [5253] = 0x54494c03, [5254] = 37,
    /* !          */ [5255] = 5252, [5256] = 0x00002101, [5257] = 38,
    /* @          */ [5258] = 5255, [5259] = 0x00004001, [5260] = 39,
    /* +!         */ [5261] = 5258, [5262] = 0x00212b02, [5263] = 40,
    /* -!         */ [5264] = 5261, [5265] = 0x00212d02, [5266] = 41,
    /* C!         */ [5267] = 5264, [5268] = 0x00214302, [5269] = 42,
    /* C@         */ [5270] = 5267, [5271] = 0x00404302, [5272] = 43,
    /* C@C!       */ [5273] = 5270, [5274] = 0x43404304, [5275] = 0x00000021, [5276] = 44,
    /* CMOVE      */ [5277] = 5273, [5278] = 0x4f4d4305, [5279] = 0x00004556, [5280] = 45,
    /* STATE      */ [5281] = 5277, [5282] = 0x41545305, [5283] = 0x00004554, [5284] = 46,
    /* HERE       */ [5285] = 5281, [5286] = 0x52454804, [5287] = 0x00000045, [5288] = 47,
    /* LATEST     */ [5289] = 5285, [5290] = 0x54414c06, [5291] = 0x00545345, [5292] = 48,
    /* S0         */ [5293] = 5289, [5294] = 0x00305302, [5295] = 49,
    /* BASE       */ [5296] = 5293, [5297] = 0x53414204, [5298] = 0x00000045, [5299] = 50,
    /* VERSION    */ [5300] = 5296, [5301] = 0x52455607, [5302] = 0x4e4f4953, [5303] = 51,
    /* R0         */ [5304] = 5300, [5305] = 0x00305202, [5306] = 52,
    /* DOCOL      */ [5307] = 5304, [5308] = 0x434f4405, [5309] = 0x00004c4f, [5310] = 53,
    /* F_IMMED    */ [5311] = 5307, [5312] = 0x495f4607, [5313] = 0x44454d4d, [5314] = 54,
    /* F_HIDDEN   */ [5315] = 5311, [5316] = 0x485f4608, [5317] = 0x45444449, [5318] = 0x0000004e, [5319] = 55,
    /* F_LENMASK  */ [5320] = 5315, [5321] = 0x4c5f4609, [5322] = 0x414d4e45, [5323] = 0x00004b53, [5324] = 56,
    /* SYS_EXIT   */ [5325] = 5320, [5326] = 0x53595308, [5327] = 0x4958455f, [5328] = 0x00000054, [5329] = 57,
    /* SYS_OPEN   */ [5330] = 5325, [5331] = 0x53595308, [5332] = 0x45504f5f, [5333] = 0x0000004e, [5334] = 58,
    /* SYS_CLOSE  */ [5335] = 5330, [5336] = 0x53595309, [5337] = 0x4f4c435f, [5338] = 0x00004553, [5339] = 59,
    /* SYS_READ   */ [5340] = 5335, [5341] = 0x53595308, [5342] = 0x4145525f, [5343] = 0x00000044, [5344] = 60,
    /* SYS_WRITE  */ [5345] = 5340, [5346] = 0x53595309, [5347] = 0x4952575f, [5348] = 0x00004554, [5349] = 61,
    /* SYS_CREAT  */ [5350] = 5345, [5351] = 0x53595309, [5352] = 0x4552435f, [5353] = 0x00005441, [5354] = 62,
    /* SYS_BRK    */ [5355] = 5350, [5356] = 0x53595307, [5357] = 0x4b52425f, [5358] = 63,
    /* O_RDONLY   */ [5359] = 5355, [5360] = 0x525f4f08, [5361] = 0x4c4e4f44, [5362] = 0x00000059, [5363] = 64,
    /* O_WRONLY   */ [5364] = 5359, [5365] = 0x575f4f08, [5366] = 0x4c4e4f52, [5367] = 0x00000059, [5368] = 65,
    /* O_RDWR     */ [5369] = 5364, [5370] = 0x525f4f06, [5371] = 0x00525744, [5372] = 66,
    /* O_CREAT    */ [5373] = 5369, [5374] = 0x435f4f07, [5375] = 0x54414552, [5376] = 67,
    /* O_EXCL     */ [5377] = 5373, [5378] = 0x455f4f06, [5379] = 0x004c4358, [5380] = 68,
    /* O_TRUNC    */ [5381] = 5377, [5382] = 0x545f4f07, [5383] = 0x434e5552, [5384] = 69,
    /* O_APPEND   */ [5385] = 5381, [5386] = 0x415f4f08, [5387] = 0x4e455050, [5388] = 0x00000044, [5389] = 70,
    /* O_NONBLOCK */ [5390] = 5385, [5391] = 0x4e5f4f0a, [5392] = 0x4c424e4f, [5393] = 0x004b434f, [5394] = 71,
    /* >R         */ [5395] = 5390, [5396] = 0x00523e02, [5397] = 72,
    /* R>         */ [5398] = 5395, [5399] = 0x003e5202, [5400] = 73,
    /* RSP@       */ [5401] = 5398, [5402] = 0x50535204, [5403] = 0x00000040, [5404] = 74,
    /* RSP!       */ [5405] = 5401, [5406] = 0x50535204, [5407] = 0x00000021, [5408] = 75,
    /* RDROP      */ [5409] = 5405, [5410] = 0x52445205, [5411] = 0x0000504f, [5412] = 76,
    /* DSP@       */ [5413] = 5409, [5414] = 0x50534404, [5415] = 0x00000040, [5416] = 77,
    /* DSP!       */ [5417] = 5413, [5418] = 0x50534404, [5419] = 0x00000021, [5420] = 78,
    /* KEY        */ [5421] = 5417, [5422] = 0x59454b03, [5423] = 79,
    /* EMIT       */ [5424] = 5421, [5425] = 0x494d4504, [5426] = 0x00000054, [5427] = 80,
    /* WORD       */ [5428] = 5424, [5429] = 0x524f5704, [5430] = 0x00000044, [5431] = 81,
    /* NUMBER     */ [5432] = 5428, [5433] = 0x4d554e06, [5434] = 0x00524542, [5435] = 82,
    /* FIND       */ [5436] = 5432, [5437] = 0x4e494604, [5438] = 0x00000044, [5439] = 83,
    /* >CFA       */ [5440] = 5436, [5441] = 0x46433e04, [5442] = 0x00000041, [5443] = 84,
    /* >DFA       */ [5444] = 5440, [5445] = 0x46443e04, [5446] = 0x00000041, [5447] = 0, [5448] = 5443, [5449] = 5179, [5450] = 5251,
    /* CREATE     */ [5451] = 5444, [5452] = 0x45524306, [5453] = 0x00455441, [5454] = 85,
    /* ,          */ [5455] = 5451, [5456] = 0x00002c01, [5457] = 86,
    /* [          */ [5458] = 5455, [5459] = 0x00005b81, [5460] = 87,
    /* ]          */ [5461] = 5458, [5462] = 0x00005d01, [5463] = 88,
    /* IMMEDIATE  */ [5464] = 5461, [5465] = 0x4d4d4989, [5466] = 0x41494445, [5467] = 0x00004554, [5468] = 89,
    /* HIDDEN     */ [5469] = 5464, [5470] = 0x44494806, [5471] = 0x004e4544, [5472] = 90,
    /* HIDE       */ [5473] = 5469, [5474] = 0x44494804, [5475] = 0x00000045, [5476] = 0, [5477] = 5431, [5478] = 5439, [5479] = 5472, [5480] = 5251,
    /* :          */ [5481] = 5473, [5482] = 0x00003a01, [5483] = 0, [5484] = 5431, [5485] = 5454, [5486] = 5254, [5487] = 0, [5488] = 5457, [5489] = 5292, [5490] = 5260, [5491] = 5472, [5492] = 5463, [5493] = 5251,
    /* ;          */ [5494] = 5481, [5495] = 0x00003b81, [5496] = 0, [5497] = 5254, [5498] = 5251, [5499] = 5457, [5500] = 5292, [5501] = 5260, [5502] = 5472, [5503] = 5460, [5504] = 5251,
    /* '          */ [5505] = 5494, [5506] = 0x00002701, [5507] = 91,
    /* BRANCH     */ [5508] = 5505, [5509] = 0x41524206, [5510] = 0x0048434e, [5511] = 92,
    /* 0BRANCH    */ [5512] = 5508, [5513] = 0x52423007, [5514] = 0x48434e41, [5515] = 93,
    /* LITSTRING  */ [5516] = 5512, [5517] = 0x54494c09, [5518] = 0x49525453, [5519] = 0x0000474e, [5520] = 94,
    /* TELL       */ [5521] = 5516, [5522] = 0x4c455404, [5523] = 0x0000004c, [5524] = 95,
    /* INTERPRET  */ [5525] = 5521, [5526] = 0x544e4909, [5527] = 0x52505245, [5528] = 0x00005445, [5529] = 96,
    /* QUIT       */ [5530] = 5525, [5531] = 0x49555104, [5532] = 0x00000054, [5533] = 0, [5534] = 5306, [5535] = 5408, [5536] = 5529, [5537] = 5511, [5538] = -8,
    /* CHAR       */ [5539] = 5530, [5540] = 0x41484304, [5541] = 0x00000052, [5542] = 97,
    /* EXECUTE    */ [5543] = 5539, [5544] = 0x45584507, [5545] = 0x45545543, [5546] = 98,
    /* SYSCALL3   */ [5547] = 5543, [5548] = 0x53595308, [5549] = 0x4c4c4143, [5550] = 0x00000033, [5551] = 99,
    /* SYSCALL2   */ [5552] = 5547, [5553] = 0x53595308, [5554] = 0x4c4c4143, [5555] = 0x00000032, [5556] = 100,
    /* SYSCALL1   */ [5557] = 5552, [5558] = 0x53595308, [5559] = 0x4c4c4143, [5560] = 0x00000031, [5561] = 101,    
};
static char *bytes = (char *)memory;

char key(void) {
    static unsigned currkey = 0x4000, buftop = 0x4000;
    ssize_t c;

    while (buftop <= currkey) {
        currkey = 0x4000;
        c = read(STDIN_FILENO, bytes + currkey, 0x1000);
        if (c < 0)
            exit(-c);
        buftop = 0x4000 + c;
    }
    return bytes[currkey++];
}

unsigned word(void) {
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

unsigned find(unsigned count, unsigned name) {
    int word = memory[0x1402]; /* LATEST */

    while (word && (((memory[word + 1] & 0x3F) != count) || memcmp(bytes + (word << 2) + 5, bytes + name, count)))
        word = memory[word];

    return word;
}

long long number(unsigned n, unsigned s) {
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

    return ((long long)n << 32) | (res * sign);
}

unsigned code_field_address(unsigned word) {
    return word + 2 + ((memory[word + 1] & 0x1F) >> 2);
}

int main(void) {
    register unsigned sp = 0x0800;
    register unsigned rsp = 0x1000;
    register unsigned cfa = 5533, ip = 0;
    register int a, b, c, d;
    long long num;

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
            case 21: /* <= */
                memory[sp + 1] = memory[sp + 1] == memory[sp];
                ++sp;
                break;
            case 22: /* < */
                memory[sp + 1] = memory[sp + 1] < memory[sp];
                ++sp;
                break;
            case 23: /* > */
                memory[sp + 1] = memory[sp + 1] > memory[sp];
                ++sp;
                break;
            case 24: /* <= */
                memory[sp + 1] = memory[sp + 1] <= memory[sp];
                ++sp;
                break;
            case 25: /* >= */
                memory[sp + 1] = memory[sp + 1] >= memory[sp];
                ++sp;
                break;
            case 26: /* 0= */
                memory[sp] = !memory[sp];
                break;
            case 27: /* 0<> */
                memory[sp] = memory[sp] != 0;
                break;
            case 28: /* 0< */
                memory[sp] = memory[sp] < 0;
                break;
            case 29: /* 0> */
                memory[sp] = memory[sp] > 0;
                break;
            case 30: /* 0<= */
                memory[sp] = memory[sp] <= 0;
                break;
            case 31: /* 0>= */
                memory[sp] = memory[sp] >= 0;
                break;
            case 32: /* AND */
                memory[sp + 1] &= memory[sp];
                ++sp;
                break;
            case 33: /* OR */
                memory[sp + 1] |= memory[sp];
                ++sp;
                break;
            case 34: /* XOR */
                memory[sp + 1] ^= memory[sp];
                ++sp;
                break;
            case 35: /* INVERT */
                memory[sp] = ~memory[sp];
                break;
            case 36: /* EXIT */
                ip = memory[rsp++];
                break;
            case 37: /* LIT */
                memory[--sp] = memory[ip++];
                break;
            case 38: /* ! */
                memory[memory[sp] >> 2] = memory[sp + 1];
                sp += 2;
                break;
            case 39: /* @ */
                memory[sp] = memory[memory[sp] >> 2];
                break;
            case 40: /* +! */
                memory[memory[sp]] += memory[sp + 1];
                sp += 2;
                break;
            case 41: /* -! */
                memory[memory[sp]] -= memory[sp + 1];
                sp += 2;
                break;
            case 42: /* C! */
                bytes[memory[sp]] = memory[sp + 1];
                sp += 2;
                break;
            case 43: /* C@ */
                memory[sp] = bytes[memory[sp]];
                break;
            case 44: /* C@C! */
                bytes[memory[sp + 1]] = bytes[memory[sp]];
                ++sp;
                break;
            case 45: /* CMOVE */
                (void)memmove(bytes + memory[sp + 1], bytes + memory[sp + 2], memory[sp]);
                sp += 2;
                break;
            case 46: /* STATE */
                memory[--sp] = 0x1400 << 2;
                break;
            case 47: /* HERE */
                memory[--sp] = 0x1401 << 2;
                break;
            case 48: /* LATEST */
                memory[--sp] = 0x1402 << 2;
                break;
            case 49: /* S0 */
                memory[--sp] = 0x1403 << 2;
                break;
            case 50: /* BASE */
                memory[--sp] = 0x1404 << 2;
                break;
            case 51: /* VERSION */
                memory[--sp] = 47;
                break;
            case 52: /* R0 */
                memory[--sp] = 0x1000;
                break;
            case 53: /* DOCOL */
                memory[--sp] = 0;
                break;
            case 54: /* F_IMMED */
                memory[--sp] = 0x80;
                break;
            case 55: /* F_HIDDEN */
                memory[--sp] = 0x20;
                break;
            case 56: /* F_LENMASK */
                memory[--sp] = 0x1F;
                break;
            case 57: /* SYS_EXIT */
                memory[--sp] = SYS_exit;
                break;
            case 58: /* SYS_OPEN */
                memory[--sp] = SYS_open;
                break;
            case 59: /* SYS_CLOSE */
                memory[--sp] = SYS_close;
                break;
            case 60: /* SYS_READ */
                memory[--sp] = SYS_read;
                break;
            case 61: /* SYS_WRITE */
                memory[--sp] = SYS_write;
                break;
            case 62: /* SYS_CREAT */
                memory[--sp] = SYS_creat;
                break;
            case 63: /* SYS_BRK */
                memory[--sp] = SYS_brk;
                break;
            case 64: /* O_RDONLY */
                memory[--sp] = O_RDONLY;
                break;
            case 65: /* O_WRONLY */
                memory[--sp] = O_WRONLY;
                break;
            case 66: /* O_RDWR */
                memory[--sp] = O_RDWR;
                break;
            case 67: /* O_CREAT */
                memory[--sp] = O_CREAT;
                break;
            case 68: /* O_EXCL */
                memory[--sp] = O_EXCL;
                break;
            case 69: /* O_TRUNC */
                memory[--sp] = O_TRUNC;
                break;
            case 70: /* O_APPEND */
                memory[--sp] = O_APPEND;
                break;
            case 71: /* O_NONBLOCK */
                memory[--sp] = O_NONBLOCK;
                break;
            case 72: /* >R */
                memory[--rsp] = memory[sp++];
                break;
            case 73: /* R> */
                memory[--sp] = memory[rsp++];
                break;
            case 74: /* RSP@ */
                memory[--sp] = rsp;
                break;
            case 75: /* RSP! */
                rsp = memory[sp++];
                break;
            case 76: /* RDROP */
                ++rsp;
                break;
            case 77: /* DSP@ */
                --sp;
                memory[sp] = sp + 1;
                break;
            case 78: /* DSP! */
                sp = memory[sp];
                break;
            case 79: /* KEY */
                memory[--sp] = key();
                break;
            case 80: /* EMIT */
                (void)(write(STDOUT_FILENO, bytes + (sp++ << 2), 1) + 1);
                break;
            case 81: /* WORD */
                memory[--sp] = 0x5014;
                memory[--sp] = word();
                break;
            case 82: /* NUMBER */
                num = number(memory[sp], memory[sp + 1]);
                memory[sp + 1] = num & 0xFFFFFFFF;
                memory[sp + 0] = (num >> 32);
                break;
            case 83: /* FIND */
                memory[sp + 1] = find(memory[sp], memory[sp + 1]);
                ++sp;
                break;
            case 84: /* >CFA */
                memory[sp] = code_field_address(memory[sp]);
                break;
            case 85: /* CREATE */
                a = (memory[0x1401] + 3) >> 2;
                memory[a] = memory[0x1402];
                memory[a + 1] = memory[sp];
                memcpy(bytes + (a << 2) + 5, bytes + memory[sp + 1], memory[sp]);
                memory[0x1401] = code_field_address(a) << 2;
                memory[0x1402] = a;
                sp += 2;
                break;
            case 86: /* , */
                memory[memory[0x1401] >> 2] = memory[sp++];
                memory[0x1401] += 4;
                break;
            case 87: /* [ */
                memory[0x1400] = 0;
                break;
            case 88: /* ] */
                memory[0x1400] = 1;
                break;
            case 89: /* IMMEDIATE */
                memory[memory[0x1402] + 1] ^= 0x80;
                break;
            case 90: /* HIDDEN */
                memory[memory[sp++] + 1] ^= 0x20;
                break;
            case 91: /* ' */
                memory[--sp] = memory[ip++];
                break;
            case 92: /* BRANCH */
                ip += memory[ip] >> 2;
                break;
            case 93: /* 0BRANCH */
                ip += memory[sp++] ? 1 : memory[ip] >> 2;
                break;
            case 94: /* LITSTRING */
                memory[--sp] = memory[ip + 1];
                memory[--sp] = memory[ip + 0];
                ip += 2 + ((memory[ip] + 3) >> 2);
                break;
            case 95: /* TELL */
                (void)(write(STDOUT_FILENO, bytes + memory[sp + 1], memory[sp]) + 1);
                sp += 2;
                break;
            case 96: /* INTERPRET */
                a = word();
                b = find(a, 0x5014);
                if (b) {
                    cfa = code_field_address(b);
                    if ((memory[b + 1] & 0x80) || !memory[0x1400])
                        continue;
                    memory[memory[0x1401] >> 2] = cfa;
                    memory[0x1401] += 4;
                } else {
                    num = number(a, 0x5014);
                    if (num >> 32) {
                        (void)(write(STDERR_FILENO, "PARSE ERROR: ", 13) + 1);
                        (void)(write(STDERR_FILENO, bytes + 0x5014, a) + 1);
                        (void)(write(STDERR_FILENO, "\n", 1) + 1);
                    } else if (memory[0x1400]) {
                        memory[memory[0x1401] >> 2] = 5254; /* LIT */
                        memory[0x1401] += 4;
                        memory[memory[0x1401] >> 2] = num & 0xFFFFFFFF;
                        memory[0x1401] += 4;
                    } else {
                        memory[--sp] = num & 0xFFFFFFFF;
                    }
                }
                break;
            case 97: /* CHAR */
                word();
                memory[--sp] = bytes[0x5014];
                break;
            case 98: /* EXECUTE */
                cfa = memory[sp++];
                continue;
            case 99: /* SYSCALL3 */
                memory[sp + 3] = syscall(memory[sp], memory[sp + 1], memory[sp + 2], memory[sp + 3]);
                sp += 3;
                break;
            case 100: /* SYSCALL2 */
                memory[sp + 2] = syscall(memory[sp], memory[sp + 1], memory[sp + 2]);
                sp += 2;
                break;
            case 101: /* SYSCALL1 */
                memory[sp + 1] = syscall(memory[sp], memory[sp + 1]);
                sp += 1;
                break;
            }
        cfa = memory[ip++];
    }
    return cfa;
}