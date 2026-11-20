# MIRACL 한국어 소규모 검색 평가셋

MIRACL 한국어 dev에서 질문 50개를 선택하고, 검색 대상 문단 1,000개를 구성했다. 각 문단은 원본의 `docid`, `title`, `text`를 유지한다. `title`은 위키백과 문서 제목이고 `text`는 해당 문서의 문단이다. 같은 원본 문서에 속한 문단들은 제목을 공유한다.

| 항목 | 개수 |
|---|---:|
| 평가 질문 | 50 |
| 검색 대상 문단 | 1,000 |
| 원본에서 관련성을 판정한 문단 | 711 |
| 추가로 선택한 문단 | 289 |
| 질문과 문단의 관련성 판정 | 716 |
| 관련성 1 판정 | 117 |
| 관련성 0 판정 | 599 |

## 파일

| 파일 | 필드와 역할 |
|---|---|
| `corpus.jsonl` | `docid`, `title`, `text`. 색인에 넣을 문단 |
| `queries.jsonl` | `query_id`, `text`. 검색에 사용할 질문 |
| `qrels.jsonl` | `query_id`, `docid`, `relevance`. 질문별 문단 관련성 |
| `qrels.tsv` | `query_id Q0 docid relevance`를 탭으로 구분한 TREC qrels |
| `metadata.json` | 원본 리비전, 선택 방식, 개수, 파일 크기, SHA256 |
| `SOURCE-miracl-README.md` | 질문과 라벨 원본의 데이터 카드, 출처와 인용 정보 |
| `SOURCE-corpus-README.md` | 코퍼스 원본의 데이터 카드, 출처와 인용 정보 |

JSONL 파일은 UTF-8로 저장하며 한 줄에 객체 하나를 담는다. 관련성 1은 관련 문단, 0은 원본에서 관련 없다고 판정한 문단을 의미한다. qrels에 없는 질문과 문단 조합은 미판정이다.

## 선택 방식

1. 한국어 dev 질문 213개에서 Python `random.Random(42).sample`로 50개를 선택했다.
2. 선택한 질문에 연결된 원본 관련성 판정 716건을 모두 유지했다.
3. 해당 판정이 참조하는 문단 711개를 모두 포함했다. 관련 문단과 원본에서 관련 없다고 판정한 문단을 함께 포함한다.
4. 나머지 코퍼스에서 `SHA256("42:" + docid)`가 작은 순서로 289개를 추가했다.
5. 문단 ID 중복, 제목과 본문 누락, 관련성 판정이 참조하는 문단 누락을 검사했다. 모든 질문에 관련성 1 문단이 포함되는 것을 확인했다.

추출 스크립트는 저장소 루트의 `scripts/build_miracl_ko_small.py`다. Python 표준 라이브러리로 실행하며 고정한 원본 리비전의 한국어 압축 파일 3개, 약 226 MB를 스트리밍한다. 출력할 문단을 메모리에 유지하고 결과 파일을 저장한다.

```powershell
python scripts/build_miracl_ko_small.py
```

## 평가 방법

`corpus.jsonl`의 1,000개 문단 전체를 색인에 넣고 `queries.jsonl`의 질문을 검색한다. 반환한 문단의 `docid`를 qrels와 연결하여 Recall@5, Recall@10, nDCG@10, MRR@10을 계산한다. 원본의 관련성 0 판정과 미판정 상태는 구분하여 보존한다.

제목 사용 효과는 같은 코퍼스와 질문에 대해 본문 검색, 제목과 본문을 합친 검색, 제목에 별도 가중치를 준 검색으로 비교할 수 있다.

이 평가셋은 1,000개 문단에서 검색 방식을 비교하는 용도로 사용한다. 검색 후보 수와 분포가 원본 약 149만 문단과 다르므로 점수는 이 평가셋의 결과로 보고한다. 질문과 근거 문단, 관련성 라벨로 검색을 평가하며, 생성 답변 정확도를 평가하려면 참조 답변을 별도로 작성한다.

## 출처

- 질문과 라벨: https://huggingface.co/datasets/miracl/miracl
- 제목과 본문: https://huggingface.co/datasets/miracl/miracl-corpus
- 공식 저장소와 논문 인용: https://github.com/project-miracl/miracl

원본 데이터 카드의 라이선스 표기는 Apache-2.0이다. 원본 데이터 카드와 문서 ID를 함께 보존했으며, 위키백과 텍스트의 출처와 이용 조건은 원본 제공처를 따른다.
