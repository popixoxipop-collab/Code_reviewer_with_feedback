# Java Curriculum NVIDIA Parallel Pipeline Run

- PDF: `/Users/xox/Downloads/AI_JAVA_교안.pdf`
- Model: `qwen/qwen3-next-80b-a3b-instruct`
- Chunk size: `10` pages
- Chunks processed: `26`
- Max workers: `4`
- Dry run: `False`
- Elapsed: `300.3s`
- NVIDIA key slots used: `{'NVIDIA_API_KEY_1': 5, 'NVIDIA_API_KEY_2': 4, 'NVIDIA_API_KEY_3': 4, 'NVIDIA_API_KEY_4': 4, 'NVIDIA_API_KEY_5': 4, 'NVIDIA_API_KEY_6': 4, 'NVIDIA_API_KEY_7': 4}`
- Rate policy: `{'capacity_per_key_per_model_per_60s': 20, 'key_slots': 7, 'aggregate_capacity_per_model_per_60s': 140, 'window_s': 60.0}`
- Rate policy respected: `True`

## Verified Pipeline

1. PDF pages were extracted with `pdftotext`.
2. Each page range was sent as an independent chunk call through `NvidiaRotatingClient`.
3. `CountingNvidiaKeyPool` rotated calls across `NVIDIA_API_KEY_1..N` and recorded slot counts only, never key values.
4. Chunk outputs preserved `source_pages` for every concept/code/caution node.
5. A NVIDIA refinement loop audited page provenance and graph readiness.
6. A graphify-compatible `graphify-out/graph.json` was built from unit/concept/page/refine/question state.
7. Final questions were generated from graph nodes and cite `source_node_ids` plus concrete `source_pages`.

## Outputs

- `chunks.json`
- `unit_map.json`
- `refine_audit.json`
- `questions.json`
- `rate_audit.json`
- `graphify-out/graph.json`
- `graphify-out/GRAPH_REPORT.md`

## Counts

- Units: `8`
- Concepts/code/cautions: `476`
- Graph nodes: `693`
- Graph links: `1096`
- Questions: `5`

## Refine Loop

- Iteration `1`: `needs_refine` — Unit covers broad Java fundamentals from syntax to OOP, but has critical issues with concept duplication, missing page provenance for key topics, and checklist failures.
- Iteration `2`: `needs_refine` — Unit covers foundational Java concepts from syntax to OOP, but has critical issues with duplicate concepts, missing page provenance for key topics, and inconsistent granularity.

## NVIDIA Rate Audit

- `NVIDIA_API_KEY_1::qwen/qwen3-next-80b-a3b-instruct`: calls `4`, max 60s `2` / limit `20`, within `True`
- `NVIDIA_API_KEY_2::qwen/qwen3-next-80b-a3b-instruct`: calls `4`, max 60s `2` / limit `20`, within `True`
- `NVIDIA_API_KEY_3::qwen/qwen3-next-80b-a3b-instruct`: calls `4`, max 60s `2` / limit `20`, within `True`
- `NVIDIA_API_KEY_4::qwen/qwen3-next-80b-a3b-instruct`: calls `4`, max 60s `2` / limit `20`, within `True`
- `NVIDIA_API_KEY_5::qwen/qwen3-next-80b-a3b-instruct`: calls `4`, max 60s `2` / limit `20`, within `True`
- `NVIDIA_API_KEY_6::qwen/qwen3-next-80b-a3b-instruct`: calls `3`, max 60s `2` / limit `20`, within `True`
- `NVIDIA_API_KEY_7::qwen/qwen3-next-80b-a3b-instruct`: calls `3`, max 60s `2` / limit `20`, within `True`
- aggregate `qwen/qwen3-next-80b-a3b-instruct`: calls `26`, max 60s `10` / limit `140`, within `True`

## Sample Questions

- Unit 01: 다음 코드에서 '=='과 'equals()'를 각각 사용해 문자열을 비교할 때 어떤 차이가 발생합니까? 실제 프로그램에서 잘못 사용하면 어떤 버그가 생길 수 있나요? (출처: pages 51-52) (pages: [51, 52])
- Unit 01: 전위 증감 연산자(++a)와 후위 증감 연산자(a++)가 다음 코드에서 각각 어떤 값을 출력합니까? 왜 이 차이가 발생하며, 이 차이를 무시하면 반복문이나 수식에서 어떤 오류가 생길 수 있나요? (출처: pages 79-80)
int a = 5;
System.out.println(a++);
System.out.println(++a); (pages: [79, 80])
- Unit 01: 다음 코드에서 switch 문에 break를 생략하면 어떤 결과가 발생합니까? 예를 들어, case 1에서 break를 없애면 case 2와 default도 실행되는 이유는 무엇이며, 이는 실제 개발에서 어떤 버그를 유발할 수 있나요? (출처: pages 104-105)
switch (day) {
  case 1:
    System.out.println("월");
  case 2:
    System.out.println("화");
    break;
  default:
    System.out.println("기타");
} (pages: [104, 105])
- Unit 01: 정수형 변수에 double 값을 대입할 때 자동 형 변환은 왜 불가능합니까? 반대로 double에 int를 대입할 때는 가능한 이유는 무엇이며, 명시적 캐스팅을 하면 어떤 정보 손실이 발생할 수 있나요? (출처: pages 55-56) (pages: [55, 56])
- Unit 01: static 메서드에서 인스턴스 변수를 직접 참조할 수 없는 이유는 무엇이며, 이 제한이 Java의 객체지향 설계 원칙(캡슐화, 인스턴스 독립성)과 어떻게 연결되나요? (출처: pages 181) (pages: [181])

## Graphify Query Smoke Test

```text
NODE Unit 01 Java 시작하기 [src= loc= community=]
NODE Unit 02 변수와자료형 [src= loc= community=]
NODE Unit 03 사용자로부터입력받기 [src= loc= community=]
NODE Unit 04 Java 의 연산자 [src= loc= community=]
NODE p51 [src= loc= community=]
NODE p52 [src= loc= community=]
NODE p145 [src= loc= community=]
NODE p57 [src= loc= community=]
NODE p144 [src= loc= community=]
NODE Unit 07 배열 [src= loc= community=]
NODE AI_JAVA_교안.pdf [src= loc= community=]
NODE Unit 08 메소드 [src= loc= community=]
NODE Unit 05 조건문 [src= loc= community=]
NODE p88 [src= loc= community=]
NODE p101 [src= loc= community=]
NODE Unit 06 반복문 [src= loc= community=]
NODE p85 [src= loc= community=]
NODE p191 [src= loc= community=]
NODE p25 [src= loc= community=]
NODE p141 [src= loc= community=]
NODE p181 [src= loc= community=]
NODE p104 [src= loc= community=]
NODE p221 [src= loc= community=]
NODE p64 [src= loc= community=]
NODE p150 [src= loc= community=]
NODE p183 [src= loc= community=]
NODE p148 [src= loc= community=]
NODE p149 [src= loc= community=]
NODE p143 [src= loc= community=]
NODE p179 [src= loc= community=]
NODE p121 [src= loc= community=]
NODE p89 [src= loc= community=]
NODE p91 [src= loc= community=]
NODE p14 [src= loc= community=]
NODE p59 [src= loc= community=]
NODE p4 [src= loc= community=]
NODE 도트 연산자 [src= loc= community=]
NODE p199 [src= loc= community=]
NODE p201 [src= loc= community=]
NODE p140 [src= loc= community=]
NODE p225 [src= loc= community=]
NODE p23 [src= loc= community=]
NODE p71 [src= loc= community=]
NODE 전위 vs 후위 증감 연산자 [src= loc= community=]
NODE p137 [src= loc= community=]
NODE p81 [src= loc= community=]
NODE p125 [src= loc= community=]
NODE p72 [src= loc= community=]
NODE p186 [src= loc= community=]
NODE p77 [src= loc= community=]
NODE p241 [src= loc= community=]
NODE p173 [src= loc= community=]
NODE p128 [src= loc= community=]
NODE p86 [src= loc= community=]
NODE p33 [src= loc= community=]
NODE p8 [src= loc= community=]
NODE p223 [src= loc= community=]
NODE p55 [src= loc= community=]
NODE p105 [src= loc= community=]
NODE p126 [src= loc= community=]
NODE p84 [src= loc= community=]
NODE p56 [src= loc= community=]
NODE p62 [src= loc= community=]
NODE p63 [src= loc= community=]
NODE p30 [src= loc= community=]
NODE p82 [src= loc= community=]
NODE p26 [src= loc= community=]
NODE p174 [src= loc= community=]
NODE static 메서드에서 인스턴스 변수를 직접 참조할 수 없는 이유는 무엇이며, 이 제한이 Java의 객체지향 설계 원칙(캡슐화, 인스턴스 독립성
... (truncated to ~800 token budget)
```
