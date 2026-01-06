use std::io::{self, Read, Write};
use std::process;

const BUFFER_START: usize = 0x4000;
const BUFFER_SIZE: usize = 0x1000;
const WORD_BUFFER: usize = 0x5014;
const STATE_ADDR: usize = 0x1400;
const HERE_ADDR: usize = 0x1401;
const LATEST_ADDR: usize = 0x1402;
const S0_ADDR: usize = 0x1403;
const BASE_ADDR: usize = 0x1404;

#[derive(Default)]
struct NumResult {
    result: i32,
    remaining: i32,
}

struct Forth {
    memory: Vec<u8>,
    currkey: usize,
    buftop: usize,
}

impl Forth {
    fn new() -> io::Result<Self> {
        let mut memory = vec![0u8; 0x10000 * 4];
        
        // Initialize the rodata section
        Self::init_rodata(&mut memory);
        
        Ok(Self {
            memory,
            currkey: BUFFER_START,
            buftop: BUFFER_START,
        })
    }

    fn init_rodata(memory: &mut [u8]) {
        let rodata: [(usize, i32); 431] = [
            (5120, 0), (5121, 5559 << 2), (5122, 5554 << 2), (5123, 2048 << 2), (5124, 10),
            (5133, 0 << 2), (5134, 0x4f524404), (5135, 0x00000050), (5136, 1),
            (5137, 5133 << 2), (5138, 0x41575304), (5139, 0x00000050), (5140, 2),
            (5141, 5137 << 2), (5142, 0x50554403), (5143, 3),
            (5144, 5141 << 2), (5145, 0x45564f04), (5146, 0x00000052), (5147, 4),
            (5148, 5144 << 2), (5149, 0x544f5203), (5150, 5),
            (5151, 5148 << 2), (5152, 0x4f522d04), (5153, 0x00000054), (5154, 6),
            (5155, 5151 << 2), (5156, 0x52443205), (5157, 0x0000504f), (5158, 7),
            (5159, 5155 << 2), (5160, 0x55443204), (5161, 0x00000050), (5162, 8),
            (5163, 5159 << 2), (5164, 0x57533205), (5165, 0x00005041), (5166, 9),
            (5167, 5163 << 2), (5168, 0x55443f04), (5169, 0x00000050), (5170, 10),
            (5171, 5167 << 2), (5172, 0x002b3102), (5173, 11),
            (5174, 5171 << 2), (5175, 0x002d3102), (5176, 12),
            (5177, 5174 << 2), (5178, 0x002b3402), (5179, 13),
            (5180, 5177 << 2), (5181, 0x002d3402), (5182, 14),
            (5183, 5180 << 2), (5184, 0x00002b01), (5185, 15),
            (5186, 5183 << 2), (5187, 0x00002d01), (5188, 16),
            (5189, 5186 << 2), (5190, 0x00002a01), (5191, 17),
            (5192, 5189 << 2), (5193, 0x4f4d2f04), (5194, 0x00000044), (5195, 18),
            (5196, 5192 << 2), (5197, 0x00003d01), (5198, 19),
            (5199, 5196 << 2), (5200, 0x003e3c02), (5201, 20),
            (5202, 5199 << 2), (5203, 0x00003c01), (5204, 21),
            (5205, 5202 << 2), (5206, 0x00003e01), (5207, 22),
            (5208, 5205 << 2), (5209, 0x003d3c02), (5210, 23),
            (5211, 5208 << 2), (5212, 0x003d3e02), (5213, 24),
            (5214, 5211 << 2), (5215, 0x003d3002), (5216, 25),
            (5217, 5214 << 2), (5218, 0x3e3c3003), (5219, 26),
            (5220, 5217 << 2), (5221, 0x003c3002), (5222, 27),
            (5223, 5220 << 2), (5224, 0x003e3002), (5225, 28),
            (5226, 5223 << 2), (5227, 0x3d3c3003), (5228, 29),
            (5229, 5226 << 2), (5230, 0x3d3e3003), (5231, 30),
            (5232, 5229 << 2), (5233, 0x444e4103), (5234, 31),
            (5235, 5232 << 2), (5236, 0x00524f02), (5237, 32),
            (5238, 5235 << 2), (5239, 0x524f5803), (5240, 33),
            (5241, 5238 << 2), (5242, 0x564e4906), (5243, 0x00545245), (5244, 34),
            (5245, 5241 << 2), (5246, 0x49584504), (5247, 0x00000054), (5248, 35),
            (5249, 5245 << 2), (5250, 0x54494c03), (5251, 36),
            (5252, 5249 << 2), (5253, 0x00002101), (5254, 37),
            (5255, 5252 << 2), (5256, 0x00004001), (5257, 38),
            (5258, 5255 << 2), (5259, 0x00212b02), (5260, 39),
            (5261, 5258 << 2), (5262, 0x00212d02), (5263, 40),
            (5264, 5261 << 2), (5265, 0x00214302), (5266, 41),
            (5267, 5264 << 2), (5268, 0x00404302), (5269, 42),
            (5270, 5267 << 2), (5271, 0x43404304), (5272, 0x00000021), (5273, 43),
            (5274, 5270 << 2), (5275, 0x4f4d4305), (5276, 0x00004556), (5277, 44),
            (5278, 5274 << 2), (5279, 0x41545305), (5280, 0x00004554), (5281, 45),
            (5282, 5278 << 2), (5283, 0x52454804), (5284, 0x00000045), (5285, 46),
            (5286, 5282 << 2), (5287, 0x54414c06), (5288, 0x00545345), (5289, 47),
            (5290, 5286 << 2), (5291, 0x00305302), (5292, 48),
            (5293, 5290 << 2), (5294, 0x53414204), (5295, 0x00000045), (5296, 49),
            (5297, 5293 << 2), (5298, 0x52455607), (5299, 0x4e4f4953), (5300, 50),
            (5301, 5297 << 2), (5302, 0x00305202), (5303, 51),
            (5304, 5301 << 2), (5305, 0x434f4405), (5306, 0x00004c4f), (5307, 52),
            (5308, 5304 << 2), (5309, 0x495f4607), (5310, 0x44454d4d), (5311, 53),
            (5312, 5308 << 2), (5313, 0x485f4608), (5314, 0x45444449), (5315, 0x0000004e), (5316, 54),
            (5317, 5312 << 2), (5318, 0x4c5f4609), (5319, 0x414d4e45), (5320, 0x00004b53), (5321, 55),
            (5322, 5317 << 2), (5323, 0x53595308), (5324, 0x4958455f), (5325, 0x00000054), (5326, 56),
            (5327, 5322 << 2), (5328, 0x53595308), (5329, 0x45504f5f), (5330, 0x0000004e), (5331, 57),
            (5332, 5327 << 2), (5333, 0x53595309), (5334, 0x4f4c435f), (5335, 0x00004553), (5336, 58),
            (5337, 5332 << 2), (5338, 0x53595308), (5339, 0x4145525f), (5340, 0x00000044), (5341, 59),
            (5342, 5337 << 2), (5343, 0x53595309), (5344, 0x4952575f), (5345, 0x00004554), (5346, 60),
            (5347, 5342 << 2), (5348, 0x53595309), (5349, 0x4552435f), (5350, 0x00005441), (5351, 61),
            (5352, 5347 << 2), (5353, 0x53595307), (5354, 0x4b52425f), (5355, 62),
            (5356, 5352 << 2), (5357, 0x525f4f08), (5358, 0x4c4e4f44), (5359, 0x00000059), (5360, 63),
            (5361, 5356 << 2), (5362, 0x575f4f08), (5363, 0x4c4e4f52), (5364, 0x00000059), (5365, 64),
            (5366, 5361 << 2), (5367, 0x525f4f06), (5368, 0x00525744), (5369, 65),
            (5370, 5366 << 2), (5371, 0x435f4f07), (5372, 0x54414552), (5373, 66),
            (5374, 5370 << 2), (5375, 0x455f4f06), (5376, 0x004c4358), (5377, 67),
            (5378, 5374 << 2), (5379, 0x545f4f07), (5380, 0x434e5552), (5381, 68),
            (5382, 5378 << 2), (5383, 0x415f4f08), (5384, 0x4e455050), (5385, 0x00000044), (5386, 69),
            (5387, 5382 << 2), (5388, 0x4e5f4f0a), (5389, 0x4c424e4f), (5390, 0x004b434f), (5391, 70),
            (5392, 5387 << 2), (5393, 0x00523e02), (5394, 71),
            (5395, 5392 << 2), (5396, 0x003e5202), (5397, 72),
            (5398, 5395 << 2), (5399, 0x50535204), (5400, 0x00000040), (5401, 73),
            (5402, 5398 << 2), (5403, 0x50535204), (5404, 0x00000021), (5405, 74),
            (5406, 5402 << 2), (5407, 0x52445205), (5408, 0x0000504f), (5409, 75),
            (5410, 5406 << 2), (5411, 0x50534404), (5412, 0x00000040), (5413, 76),
            (5414, 5410 << 2), (5415, 0x50534404), (5416, 0x00000021), (5417, 77),
            (5418, 5414 << 2), (5419, 0x59454b03), (5420, 78),
            (5421, 5418 << 2), (5422, 0x494d4504), (5423, 0x00000054), (5424, 79),
            (5425, 5421 << 2), (5426, 0x524f5704), (5427, 0x00000044), (5428, 80),
            (5429, 5425 << 2), (5430, 0x4d554e06), (5431, 0x00524542), (5432, 81),
            (5433, 5429 << 2), (5434, 0x4e494604), (5435, 0x00000044), (5436, 82),
            (5437, 5433 << 2), (5438, 0x46433e04), (5439, 0x00000041), (5440, 83),
            (5441, 5437 << 2), (5442, 0x46443e04), (5443, 0x00000041), (5444, 0), (5445, 5440 << 2), (5446, 5179 << 2), (5447, 5248 << 2),
            (5448, 5441 << 2), (5449, 0x45524306), (5450, 0x00455441), (5451, 84),
            (5452, 5448 << 2), (5453, 0x00002c01), (5454, 85),
            (5455, 5452 << 2), (5456, 0x00005b81), (5457, 86),
            (5458, 5455 << 2), (5459, 0x00005d01), (5460, 87),
            (5461, 5458 << 2), (5462, 0x4d4d4989), (5463, 0x41494445), (5464, 0x00004554), (5465, 88),
            (5466, 5461 << 2), (5467, 0x44494806), (5468, 0x004e4544), (5469, 89),
            (5470, 5466 << 2), (5471, 0x44494804), (5472, 0x00000045), (5473, 0), (5474, 5428 << 2), (5475, 5436 << 2), (5476, 5469 << 2), (5477, 5248 << 2),
            (5478, 5470 << 2), (5479, 0x00003a01), (5480, 0), (5481, 5428 << 2), (5482, 5451 << 2), (5483, 5251 << 2), (5484, 0), (5485, 5454 << 2), (5486, 5289 << 2), (5487, 5257 << 2), (5488, 5469 << 2), (5489, 5460 << 2), (5490, 5248 << 2),
            (5491, 5478 << 2), (5492, 0x00003b81), (5493, 0), (5494, 5251 << 2), (5495, 5248 << 2), (5496, 5454 << 2), (5497, 5289 << 2), (5498, 5257 << 2), (5499, 5469 << 2), (5500, 5457 << 2), (5501, 5248 << 2),
            (5502, 5491 << 2), (5503, 0x00002701), (5504, 90),
            (5505, 5502 << 2), (5506, 0x41524206), (5507, 0x0048434e), (5508, 91),
            (5509, 5505 << 2), (5510, 0x52423007), (5511, 0x48434e41), (5512, 92),
            (5513, 5509 << 2), (5514, 0x54494c09), (5515, 0x49525453), (5516, 0x0000474e), (5517, 93),
            (5518, 5513 << 2), (5519, 0x4c455404), (5520, 0x0000004c), (5521, 94),
            (5522, 5518 << 2), (5523, 0x544e4909), (5524, 0x52505245), (5525, 0x00005445), (5526, 95),
            (5527, 5522 << 2), (5528, 0x49555104), (5529, 0x00000054), (5530, 0), (5531, 5303 << 2), (5532, 5405 << 2), (5533, 5526 << 2), (5534, 5508 << 2), (5535, -8i32 as u32 as i32),
            (5536, 5527 << 2), (5537, 0x41484304), (5538, 0x00000052), (5539, 96),
            (5540, 5536 << 2), (5541, 0x45584507), (5542, 0x45545543), (5543, 97),
            (5544, 5540 << 2), (5545, 0x53595308), (5546, 0x4c4c4143), (5547, 0x00000033), (5548, 98),
            (5549, 5544 << 2), (5550, 0x53595308), (5551, 0x4c4c4143), (5552, 0x00000032), (5553, 99),
            (5554, 5549 << 2), (5555, 0x53595308), (5556, 0x4c4c4143), (5557, 0x00000031), (5558, 100),
        ];

        for (addr, value) in &rodata {
            let bytes = value.to_ne_bytes();
            let base = *addr * 4;
            memory[base..base + 4].copy_from_slice(&bytes);
        }
    }

    #[inline]
    fn read_i32(&self, addr: usize) -> i32 {
        let base = addr * 4;
        let slice: &[u8] = &self.memory[base..base + 4];
        let bytes: [u8; 4] = slice.try_into().expect("length mismatch");
        i32::from_ne_bytes(bytes)
    }

    #[inline]
    fn write_i32(&mut self, addr: usize, value: i32) {
        let base = addr * 4;
        let bytes = value.to_ne_bytes();
        self.memory[base..base + 4].copy_from_slice(&bytes);
    }

    fn key(&mut self) -> io::Result<u8> {
        while self.buftop <= self.currkey {
            self.currkey = BUFFER_START;
            let n = io::stdin().read(&mut self.memory[BUFFER_START..BUFFER_START + BUFFER_SIZE])?;
            self.buftop = BUFFER_START + n;
        }
        let ch = self.memory[self.currkey];
        self.currkey += 1;
        Ok(ch)
    }

    fn word(&mut self) -> io::Result<i32> {
        let mut ch = self.key()?;
        
        // Skip whitespace and handle comments
        loop {
            if ch == b'\\' {
                // Comment - skip to end of line
                loop {
                    ch = self.key()?;
                    if ch == b'\n' {
                        break;
                    }
                }
            }
            if ch > b' ' {
                break;
            }
            ch = self.key()?;
        }

        // Read word
        let mut pos = WORD_BUFFER;
        loop {
            self.memory[pos] = ch;
            pos += 1;
            ch = self.key()?;
            if ch <= b' ' {
                break;
            }
        }

        Ok((pos - WORD_BUFFER) as i32)
    }

    fn find(&self, count: i32, name: usize) -> i32 {
        let mut word = self.read_i32(LATEST_ADDR);

        while word != 0 {
            let len = self.memory[word as usize + 4] & 0x3F;
            if len == count as u8 {
                let word_name = &self.memory[word as usize + 5..word as usize + 5 + count as usize];
                let search_name = &self.memory[name..name + count as usize];
                if word_name == search_name {
                    return word;
                }
            }
            word = self.read_i32((word >> 2) as usize);
        }

        0
    }

    fn number(&self, n: i32, s: usize) -> NumResult {
        let base = self.read_i32(BASE_ADDR);
        let mut pos = s;
        let mut remaining = n;
        let mut sign = 1;
        
        // Handle sign
        match self.memory[pos] {
            b'-' => {
                sign = -1;
                remaining -= 1;
                pos += 1;
            }
            b'+' => {
                remaining -= 1;
                pos += 1;
            }
            _ => {}
        }

        let mut result = 0i32;
        while remaining > 0 {
            result = result.wrapping_mul(base);
            let ch = self.memory[pos];
            pos += 1;
            
            let mut digit = (ch as i32) - ('0' as i32);
            if digit < 0 {
                break;
            }
            if digit > 9 {
                digit -= 7; // 'A' - '0' - 10
                if digit < 10 {
                    break;
                }
            }
            if digit >= base {
                break;
            }
            result = result.wrapping_add(digit);
            remaining -= 1;
        }

        NumResult {
            result: result.wrapping_mul(sign),
            remaining,
        }
    }

    fn code_field_address(&self, mut word: i32) -> i32 {
        word += 4;
        word += ((self.memory[word as usize] & 0x1F) as i32) + 4;
        word &= !3;
        word
    }

    fn run(&mut self) -> io::Result<()> {
        // Stacks are part of self.memory
        // data_stack: 0x0000-0x07FF (first 8192 bytes, 2048 i32s)
        // return_stack: 0x0800-0x0FFF (next 8192 bytes, 2048 i32s)
        let mut sp = 0x0800usize;
        let mut rsp = 0x1000usize;
        let mut cfa = 5530usize;
        let mut ip = 0usize;

        loop {
            match self.read_i32(cfa) {
                0 => { // DOCOL
                    rsp -= 1;
                    self.write_i32(rsp, ip as i32);
                    ip = cfa + 1;
                }
                1 => { // DROP
                    sp += 1;
                }
                2 => { // SWAP
                    let a = self.read_i32(sp);
                    let b = self.read_i32(sp + 1);
                    self.write_i32(sp, b);
                    self.write_i32(sp + 1, a);
                }
                3 => { // DUP
                    sp -= 1;
                    self.write_i32(sp, self.read_i32(sp + 1));
                }
                4 => { // OVER
                    sp -= 1;
                    self.write_i32(sp, self.read_i32(sp + 2));
                }
                5 => { // ROT
                    let (a, b, c) = (self.read_i32(sp), self.read_i32(sp + 1), self.read_i32(sp + 2));
                    self.write_i32(sp + 2, b);
                    self.write_i32(sp + 1, a);
                    self.write_i32(sp, c);
                }
                6 => { // -ROT
                    let (a, b, c) = (self.read_i32(sp), self.read_i32(sp + 1), self.read_i32(sp + 2));
                    self.write_i32(sp + 2, a);
                    self.write_i32(sp + 1, c);
                    self.write_i32(sp, b);
                }
                7 => { // 2DROP
                    sp += 2;
                }
                8 => { // 2DUP
                    sp -= 2;
                    self.write_i32(sp, self.read_i32(sp + 2));
                    self.write_i32(sp + 1, self.read_i32(sp + 3));
                }
                9 => { // 2SWAP
                    let (a, b, c, d) = (self.read_i32(sp), self.read_i32(sp + 1), 
                                       self.read_i32(sp + 2), self.read_i32(sp + 3));
                    self.write_i32(sp + 3, b);
                    self.write_i32(sp + 2, a);
                    self.write_i32(sp + 1, d);
                    self.write_i32(sp, c);
                }
                10 => { // ?DUP
                    let a = self.read_i32(sp);
                    if a != 0 {
                        sp -= 1;
                        self.write_i32(sp, a);
                    }
                }
                11 => { // 1+
                    self.write_i32(sp, self.read_i32(sp).wrapping_add(1));
                }
                12 => { // 1-
                    self.write_i32(sp, self.read_i32(sp).wrapping_sub(1));
                }
                13 => { // 4+
                    self.write_i32(sp, self.read_i32(sp).wrapping_add(4));
                }
                14 => { // 4-
                    self.write_i32(sp, self.read_i32(sp).wrapping_sub(4));
                }
                15 => { // +
                    let val = self.read_i32(sp + 1).wrapping_add(self.read_i32(sp));
                    self.write_i32(sp + 1, val);
                    sp += 1;
                }
                16 => { // -
                    let val = self.read_i32(sp + 1).wrapping_sub(self.read_i32(sp));
                    self.write_i32(sp + 1, val);
                    sp += 1;
                }
                17 => { // *
                    let val = self.read_i32(sp + 1).wrapping_mul(self.read_i32(sp));
                    self.write_i32(sp + 1, val);
                    sp += 1;
                }
                18 => { // /MOD
                    let (a, b) = (self.read_i32(sp + 1), self.read_i32(sp));
                    self.write_i32(sp + 1, a % b);
                    self.write_i32(sp, a / b);
                }
                19 => { // =
                    self.write_i32(sp + 1, (self.read_i32(sp + 1) == self.read_i32(sp)) as i32);
                    sp += 1;
                }
                20 => { // <>
                    self.write_i32(sp + 1, (self.read_i32(sp + 1) != self.read_i32(sp)) as i32);
                    sp += 1;
                }
                21 => { // <
                    self.write_i32(sp + 1, (self.read_i32(sp + 1) < self.read_i32(sp)) as i32);
                    sp += 1;
                }
                22 => { // >
                    self.write_i32(sp + 1, (self.read_i32(sp + 1) > self.read_i32(sp)) as i32);
                    sp += 1;
                }
                23 => { // <=
                    self.write_i32(sp + 1, (self.read_i32(sp + 1) <= self.read_i32(sp)) as i32);
                    sp += 1;
                }
                24 => { // >=
                    self.write_i32(sp + 1, (self.read_i32(sp + 1) >= self.read_i32(sp)) as i32);
                    sp += 1;
                }
                25 => { // 0=
                    self.write_i32(sp, (self.read_i32(sp) == 0) as i32);
                }
                26 => { // 0<>
                    self.write_i32(sp, (self.read_i32(sp) != 0) as i32);
                }
                27 => { // 0<
                    self.write_i32(sp, (self.read_i32(sp) < 0) as i32);
                }
                28 => { // 0>
                    self.write_i32(sp, (self.read_i32(sp) > 0) as i32);
                }
                29 => { // 0<=
                    self.write_i32(sp, (self.read_i32(sp) <= 0) as i32);
                }
                30 => { // 0>=
                    self.write_i32(sp, (self.read_i32(sp) >= 0) as i32);
                }
                31 => { // AND
                    let val = self.read_i32(sp + 1) & self.read_i32(sp);
                    self.write_i32(sp + 1, val);
                    sp += 1;
                }
                32 => { // OR
                    let val = self.read_i32(sp + 1) | self.read_i32(sp);
                    self.write_i32(sp + 1, val);
                    sp += 1;
                }
                33 => { // XOR
                    let val = self.read_i32(sp + 1) ^ self.read_i32(sp);
                    self.write_i32(sp + 1, val);
                    sp += 1;
                }
                34 => { // INVERT
                    self.write_i32(sp, !self.read_i32(sp));
                }
                35 => { // EXIT
                    ip = self.read_i32(rsp) as usize;
                    rsp += 1;
                }
                36 => { // LIT
                    sp -= 1;
                    self.write_i32(sp, self.read_i32(ip));
                    ip += 1;
                }
                37 => { // !
                    self.write_i32((self.read_i32(sp) >> 2) as usize, self.read_i32(sp + 1));
                    sp += 2;
                }
                38 => { // @
                    let addr = (self.read_i32(sp) >> 2) as usize;
                    self.write_i32(sp, self.read_i32(addr));
                }
                39 => { // +!
                    let addr = (self.read_i32(sp) >> 2) as usize;
                    let val = self.read_i32(addr).wrapping_add(self.read_i32(sp + 1));
                    self.write_i32(addr, val);
                    sp += 2;
                }
                40 => { // -!
                    let addr = (self.read_i32(sp) >> 2) as usize;
                    let val = self.read_i32(addr).wrapping_sub(self.read_i32(sp + 1));
                    self.write_i32(addr, val);
                    sp += 2;
                }
                41 => { // C!
                    let addr = self.read_i32(sp) as usize;
                    let val = self.read_i32(sp + 1) as u8;
                    self.memory[addr] = val;
                    sp += 2;
                }
                42 => { // C@
                    let addr = self.read_i32(sp) as usize;
                    self.write_i32(sp, self.memory[addr] as i32);
                }
                43 => { // C@C!
                    let src = self.read_i32(sp) as usize;
                    let dst = self.read_i32(sp + 1) as usize;
                    self.memory[dst] = self.memory[src];
                    sp += 1;
                }
                44 => { // CMOVE
                    let src = self.read_i32(sp + 2) as usize;
                    let dst = self.read_i32(sp + 1) as usize;
                    let len = self.read_i32(sp) as usize;
                    self.memory.copy_within(src..src + len, dst);
                    sp += 2;
                }
                45 => { // STATE
                    sp -= 1;
                    self.write_i32(sp, (STATE_ADDR << 2) as i32);
                }
                46 => { // HERE
                    sp -= 1;
                    self.write_i32(sp, (HERE_ADDR << 2) as i32);
                }
                47 => { // LATEST
                    sp -= 1;
                    self.write_i32(sp, (LATEST_ADDR << 2) as i32);
                }
                48 => { // S0
                    sp -= 1;
                    self.write_i32(sp, (S0_ADDR << 2) as i32);
                }
                49 => { // BASE
                    sp -= 1;
                    self.write_i32(sp, (BASE_ADDR << 2) as i32);
                }
                50 => { // VERSION
                    sp -= 1;
                    self.write_i32(sp, 47);
                }
                51 => { // R0
                    sp -= 1;
                    self.write_i32(sp, (0x1000 << 2) as i32);
                }
                52 => { // DOCOL
                    sp -= 1;
                    self.write_i32(sp, 0);
                }
                53 => { // F_IMMED
                    sp -= 1;
                    self.write_i32(sp, 0x80);
                }
                54 => { // F_HIDDEN
                    sp -= 1;
                    self.write_i32(sp, 0x20);
                }
                55 => { // F_LENMASK
                    sp -= 1;
                    self.write_i32(sp, 0x1F);
                }
                56 => { // SYS_EXIT
                    sp -= 1;
                    self.write_i32(sp, libc::SYS_exit as i32);
                }
                57 => { // SYS_OPEN
                    sp -= 1;
                    self.write_i32(sp, libc::SYS_open as i32);
                }
                58 => { // SYS_CLOSE
                    sp -= 1;
                    self.write_i32(sp, libc::SYS_close as i32);
                }
                59 => { // SYS_READ
                    sp -= 1;
                    self.write_i32(sp, libc::SYS_read as i32);
                }
                60 => { // SYS_WRITE
                    sp -= 1;
                    self.write_i32(sp, libc::SYS_write as i32);
                }
                61 => { // SYS_CREAT
                    sp -= 1;
                    self.write_i32(sp, libc::SYS_creat as i32);
                }
                62 => { // SYS_BRK
                    sp -= 1;
                    self.write_i32(sp, libc::SYS_brk as i32);
                }
                63 => { // O_RDONLY
                    sp -= 1;
                    self.write_i32(sp, libc::O_RDONLY);
                }
                64 => { // O_WRONLY
                    sp -= 1;
                    self.write_i32(sp, libc::O_WRONLY);
                }
                65 => { // O_RDWR
                    sp -= 1;
                    self.write_i32(sp, libc::O_RDWR);
                }
                66 => { // O_CREAT
                    sp -= 1;
                    self.write_i32(sp, libc::O_CREAT);
                }
                67 => { // O_EXCL
                    sp -= 1;
                    self.write_i32(sp, libc::O_EXCL);
                }
                68 => { // O_TRUNC
                    sp -= 1;
                    self.write_i32(sp, libc::O_TRUNC);
                }
                69 => { // O_APPEND
                    sp -= 1;
                    self.write_i32(sp, libc::O_APPEND);
                }
                70 => { // O_NONBLOCK
                    sp -= 1;
                    self.write_i32(sp, libc::O_NONBLOCK);
                }
                71 => { // >R
                    rsp -= 1;
                    self.write_i32(rsp, self.read_i32(sp) >> 2);
                    sp += 1;
                }
                72 => { // R>
                    sp -= 1;
                    self.write_i32(sp, self.read_i32(rsp) << 2);
                    rsp += 1;
                }
                73 => { // RSP@
                    sp -= 1;
                    self.write_i32(sp, (rsp << 2) as i32);
                }
                74 => { // RSP!
                    rsp = (self.read_i32(sp) >> 2) as usize;
                    sp += 1;
                }
                75 => { // RDROP
                    rsp += 1;
                }
                76 => { // DSP@
                    let a = sp;
                    sp -= 1;
                    self.write_i32(sp, (a << 2) as i32);
                }
                77 => { // DSP!
                    sp = (self.read_i32(sp) >> 2) as usize;
                }
                78 => { // KEY
                    sp -= 1;
                    let ch = self.key()? as i32;
                    self.write_i32(sp, ch);
                }
                79 => { // EMIT
                    let ch = self.read_i32(sp) as u8;
                    io::stdout().write_all(&[ch])?;
                    io::stdout().flush()?;
                    sp += 1;
                }
                80 => { // WORD
                    sp -= 1;
                    self.write_i32(sp, WORD_BUFFER as i32);
                    sp -= 1;
                    let word_len = self.word()?;
                    self.write_i32(sp, word_len);
                }
                81 => { // NUMBER
                    let num = self.number(self.read_i32(sp), self.read_i32(sp + 1) as usize);
                    self.write_i32(sp + 1, num.result);
                    self.write_i32(sp, num.remaining);
                }
                82 => { // FIND
                    let result = self.find(self.read_i32(sp), self.read_i32(sp + 1) as usize);
                    self.write_i32(sp + 1, result);
                    sp += 1;
                }
                83 => { // >CFA
                    let addr = self.code_field_address(self.read_i32(sp));
                    self.write_i32(sp, addr);
                }
                84 => { // CREATE
                    let count = self.read_i32(sp) as usize;
                    let name = self.read_i32(sp + 1) as usize;
                    let here = self.read_i32(HERE_ADDR) as usize;
                    
                    self.write_i32(here >> 2, self.read_i32(LATEST_ADDR));
                    self.memory[here + 4] = count as u8;
                    self.memory.copy_within(name..name + count, here + 5);
                    
                    let new_here = self.code_field_address(here as i32);
                    self.write_i32(HERE_ADDR, new_here);
                    self.write_i32(LATEST_ADDR, here as i32);
                    sp += 2;
                }
                85 => { // ,
                    let here = self.read_i32(HERE_ADDR) as usize;
                    self.write_i32(here >> 2, self.read_i32(sp));
                    self.write_i32(HERE_ADDR, (here + 4) as i32);
                    sp += 1;
                }
                86 => { // [
                    self.write_i32(STATE_ADDR, 0);
                }
                87 => { // ]
                    self.write_i32(STATE_ADDR, 1);
                }
                88 => { // IMMEDIATE
                    let latest = (self.read_i32(LATEST_ADDR) >> 2) as usize;
                    self.write_i32(latest + 1, self.read_i32(latest + 1) ^ 0x80);
                }
                89 => { // HIDDEN
                    let word = (self.read_i32(sp) >> 2) as usize;
                    self.write_i32(word + 1, self.read_i32(word + 1) ^ 0x20);
                    sp += 1;
                }
                90 => { // '
                    sp -= 1;
                    self.write_i32(sp, self.read_i32(ip));
                    ip += 1;
                }
                91 => { // BRANCH
                    ip = (ip as i32 + (self.read_i32(ip) >> 2)) as usize;
                }
                92 => { // 0BRANCH
                    if self.read_i32(sp) != 0 {
                        ip += 1;
                    } else {
                        ip = (ip as i32 + (self.read_i32(ip) >> 2)) as usize;
                    }
                    sp += 1;
                }
                93 => { // LITSTRING
                    sp -= 1;
                    self.write_i32(sp, ((ip + 1) << 2) as i32);
                    sp -= 1;
                    let len = self.read_i32(ip);
                    self.write_i32(sp, len);
                    ip += 1 + ((len + 3) >> 2) as usize;
                }
                94 => { // TELL
                    let len = self.read_i32(sp) as usize;
                    let addr = self.read_i32(sp + 1) as usize;
                    io::stdout().write_all(&self.memory[addr..addr + len])?;
                    io::stdout().flush()?;
                    sp += 2;
                }
                95 => { // INTERPRET
                    let a = self.word()? as usize;
                    let b = self.find(a as i32, WORD_BUFFER);
                    
                    if b != 0 {
                        cfa = self.code_field_address(b) as usize;
                        if (self.memory[b as usize + 4] & 0x80) != 0 || self.read_i32(STATE_ADDR) == 0 {
                            cfa >>= 2;
                            continue;
                        }
                        let here = self.read_i32(HERE_ADDR);
                        self.write_i32(here as usize >> 2, cfa as i32);
                        self.write_i32(HERE_ADDR, here + 4);
                    } else {
                        let num = self.number(a as i32, WORD_BUFFER);
                        if num.remaining != 0 {
                            io::stderr().write_all(b"PARSE ERROR: ")?;
                            io::stderr().write_all(&self.memory[WORD_BUFFER..WORD_BUFFER + a])?;
                            io::stderr().write_all(b"\n")?;
                        } else if self.read_i32(STATE_ADDR) != 0 {
                            let here = self.read_i32(HERE_ADDR);
                            self.write_i32(here as usize >> 2, 5251 << 2); // LIT
                            self.write_i32(HERE_ADDR, here + 4);
                            let here = self.read_i32(HERE_ADDR);
                            self.write_i32(here as usize >> 2, num.result);
                            self.write_i32(HERE_ADDR, here + 4);
                        } else {
                            sp -= 1;
                            self.write_i32(sp, num.result);
                        }
                    }
                }
                96 => { // CHAR
                    self.word()?;
                    sp -= 1;
                    self.write_i32(sp, self.memory[WORD_BUFFER] as i32);
                }
                97 => { // EXECUTE
                    cfa = (self.read_i32(sp) >> 2) as usize;
                    sp += 1;
                    continue;
                }
                98 => { // SYSCALL3
                    let result = syscall3(
                        self.read_i32(sp) as i64,
                        self.read_i32(sp + 1) as i64,
                        self.read_i32(sp + 2) as i64,
                        self.read_i32(sp + 3) as i64,
                    );
                    self.write_i32(sp + 3, result as i32);
                    sp += 3;
                }
                99 => { // SYSCALL2
                    let result = syscall2(
                        self.read_i32(sp) as i64,
                        self.read_i32(sp + 1) as i64,
                        self.read_i32(sp + 2) as i64,
                    );
                    self.write_i32(sp + 2, result as i32);
                    sp += 2;
                }
                100 => { // SYSCALL1
                    let result = syscall1(
                        self.read_i32(sp) as i64,
                        self.read_i32(sp + 1) as i64,
                    );
                    if self.read_i32(sp) == libc::SYS_brk as i32 {
                        self.write_i32(sp + 1, result as i32 - self.memory.as_ptr() as i32);
                    } else {
                        self.write_i32(sp + 1, result as i32);
                    }
                    sp += 1;
                }
                opcode => {
                    return Err(io::Error::new(io::ErrorKind::InvalidData, 
                        format!("Unknown opcode: {}", opcode)));
                }
            }
            cfa = (self.read_i32(ip) >> 2) as usize;
            ip += 1;
        }
    }
}

fn syscall1(n: i64, a: i64) -> i64 {
    unsafe { libc::syscall(n, a) }
}

fn syscall2(n: i64, a: i64, b: i64) -> i64 {
    unsafe { libc::syscall(n, a, b) }
}

fn syscall3(n: i64, a: i64, b: i64, c: i64) -> i64 {
    unsafe { libc::syscall(n, a, b, c) }
}

fn main() {
    let mut forth = Forth::new().unwrap_or_else(|e| {
        eprintln!("Failed to initialize: {}", e);
        process::exit(1);
    });

    if let Err(e) = forth.run() {
        eprintln!("Runtime error: {}", e);
        process::exit(1);
    }
}
