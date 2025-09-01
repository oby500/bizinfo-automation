#!/usr/bin/env python
# -*- coding: utf-8 -*-

def test_encoding_fix():
    """인코딩 복구 테스트"""
    
    # KS_174787의 실제 깨진 파일명
    corrupted = 'ºÙÀÓ 1. 2025³âµµ ¿¹ºñÃ¢¾÷ÆÐÅ°Áö(ÀÏ¹Ý) »çÀüÀÎÅ¥º£ÀÌÆÃ ¸ðÁý°ø°í.hwp'
    
    print("원본 깨진 파일명:")
    print(repr(corrupted))
    print(corrupted)
    print()
    
    def fix_korean_encoding(corrupted_text):
        """깨진 한글을 복구하는 함수"""
        if not corrupted_text:
            return corrupted_text
            
        try:
            # 여러 인코딩 복구 시도
            encodings = [
                ('iso-8859-1', 'utf-8'),
                ('iso-8859-1', 'euc-kr'),
                ('cp1252', 'utf-8'),
                ('cp1252', 'euc-kr'),
                ('latin1', 'utf-8'),
                ('latin1', 'euc-kr')
            ]
            
            print("복구 시도:")
            for i, (from_enc, to_enc) in enumerate(encodings):
                try:
                    # 잘못 디코딩된 문자를 올바른 인코딩으로 복구
                    fixed = corrupted_text.encode(from_enc).decode(to_enc)
                    print(f"{i+1}. {from_enc} -> {to_enc}: {fixed}")
                    
                    # 한글이 포함되어 있는지 확인
                    if any('\uac00' <= char <= '\ud7af' for char in fixed):
                        print(f"   ✅ 한글 발견! 이것을 사용")
                        return fixed
                except Exception as e:
                    print(f"{i+1}. {from_enc} -> {to_enc}: 실패 ({e})")
            
            # 복구 실패 시 원본 반환
            print("   ❌ 모든 복구 시도 실패")
            return corrupted_text
            
        except Exception as e:
            print(f"인코딩 복구 실패: {e}")
            return corrupted_text
    
    fixed = fix_korean_encoding(corrupted)
    print(f"\n최종 결과:")
    print(f"원본: {corrupted}")
    print(f"복구: {fixed}")
    print(f"성공: {'✅' if fixed != corrupted else '❌'}")

if __name__ == "__main__":
    test_encoding_fix()