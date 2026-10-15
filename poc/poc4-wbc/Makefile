CC      ?= gcc
CFLAGS  ?= -O2 -std=c99 -Wall -Wextra
TARGET   = wbc_aes

all: $(TARGET)

$(TARGET): wbc_aes.c
	$(CC) $(CFLAGS) -o $@ $<

run: $(TARGET)
	./$(TARGET)

# 静态检查：确认二进制中不出现过明文密钥常量（16 字节序列 00 01 .. 0f）
check: $(TARGET)
	@echo "== 明文密钥常量检查（期望：未命中）=="
	@python3 check_key_constant.py $(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all run check clean
