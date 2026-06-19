import re
from typing import Optional

# 요일 약어를 일관되게 사용하기 위한 정규식 패턴
DAY_PATTERN = r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)'


class ScheduleNormalizer:
    """
    다양한 형식의 운항 스케줄 문자열을 표준 형식으로 변환.
    VBA로 작성된 기존 로직을 Python 환경에 맞게 재구성하고 가독성을 높임.

    주요 기능:
    - 불필요한 공백, 특수 문자, 괄호 내용 제거
    - 'TBD'와 같은 특수 케이스를 'TBD ~ TBD'로 표준화
    - '요일/요일' 형식을 '요일 ~ 요일'로 변환
    - '요일 일자' 또는 '일자 요일' 등 다양한 날짜 형식을 인식하여 '요일 일자 ~ 요일 일자' 형식으로 표준화
    """

    def normalize(self, text: str) -> str:
        """
        스케줄 문자열을 정규화하여 표준 형식으로 변환.

        Args:
            text: 정규화할 원본 스케줄 문자열.

        Returns:
            정규화된 스케줄 문자열 (예: "Mon 01 ~ Tue 03", "TBD ~ TBD", "Wed").
            처리할 수 없는 형식의 경우 빈 문자열을 반환.
        """
        # 입력 값 검증
        if not text or not text.strip():
            return ""

        # 문자열 전처리
        processed_text = self._preprocess_string(text)

        # 특수 케이스 처리 ("TBD")
        if 'TBD' in processed_text.upper():
            return "TBD ~ TBD"

        # 단일 요일 형식 처리
        if re.fullmatch(DAY_PATTERN, processed_text, re.IGNORECASE):
            return self._capitalize_day(processed_text)

        # 요일 구분자 변경 ("/" -> "~")
        processed_text = re.sub(
            rf'{DAY_PATTERN}\s*/\s*{DAY_PATTERN}',
            r'\1 ~ \2',
            processed_text,
            flags=re.IGNORECASE
        )

        # 주요 스케줄 패턴 분석 및 변환
        normalized_schedule = self._parse_schedule_range(processed_text)
        if normalized_schedule:
            return normalized_schedule

        # 처리 불가 케이스
        return ""

    def _preprocess_string(self, text: str) -> str:
        """입력된 문자열의 기본적인 전처리"""
        # 공백 및 줄바꿈 통일
        s = text.replace('\n', ' ').replace('\r', ' ').replace(' ', ' ')
        # 특수 문자 제거/대체
        s = s.replace('"', '').replace('?', '-')
        # 괄호 및 내용 제거
        s = re.sub(r'\([^)]*\)', ' ', s)
        # 다중 공백 단일화
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    def _capitalize_day(self, day_str: str) -> str:
        """요일 문자열 첫 글자 대문자화 (예: 'mon' -> 'Mon')"""
        if not day_str:
            return ""
        # capitalize()로 첫 글자 대문자화
        return day_str[:3].capitalize()

    def _format_range_part(self, day: str, date: Optional[str]) -> str:
        """'요일'과 '일자'를 표준 형식('요일 일자')으로 결합"""
        capitalized_day = self._capitalize_day(day)
        if date:
            # 일자 포맷팅 (2자리, zero-padding)
            return f"{capitalized_day} {int(date):02d}"
        return capitalized_day

    def _parse_schedule_range(self, text: str) -> str:
        """'시작 ~ 끝' 형식의 스케줄 파싱 및 표준화"""
        # 패턴 1: (일자) (요일) ~ (일자) (요일)
        # 예: "25 Mon ~ 28 Tue", "Mon ~ Fri" (일자는 선택 사항)
        pattern1 = re.compile(
            r'(\d{1,2})?\s*' + DAY_PATTERN +
            r'\s*[~\-]\s*' +
            r'(\d{1,2})?\s*' + DAY_PATTERN,
            re.IGNORECASE
        )

        # 패턴 2: (요일) (일자) ~ (요일) (일자)
        # 예: "Mon 25 ~ Tue 28", "Mon ~ Fri" (일자는 선택 사항)
        pattern2 = re.compile(
            DAY_PATTERN + r'\s*(\d{1,2})?' +
            r'\s*[~\-]\s*' +
            DAY_PATTERN + r'\s*(\d{1,2})?',
            re.IGNORECASE
        )

        # 패턴별 일치 항목 검색 및 처리
        for pattern in [pattern1, pattern2]:
            matches = list(pattern.finditer(text))
            if matches:
                parts = []
                for match in matches:
                    # 그룹 순서에 따른 요일/일자 추출
                    if pattern == pattern1:
                        date1, day1, date2, day2 = match.groups()
                    else:  # pattern2
                        day1, date1, day2, date2 = match.groups()

                    # 시작/끝 부분 표준 형식으로 변환
                    part1 = self._format_range_part(day1, date1)
                    part2 = self._format_range_part(day2, date2)
                    parts.append(f"{part1} ~ {part2}")
                return " ".join(parts)

        return ""
