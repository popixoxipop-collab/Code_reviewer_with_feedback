# Java Curriculum NVIDIA Parallel Pipeline Run

- PDF: `/Users/xox/Downloads/AI_JAVA_교안.pdf`
- Model: `qwen/qwen3-next-80b-a3b-instruct`
- Chunk size: `10` pages
- Chunks processed: `26`
- Max workers: `4`
- Dry run: `False`
- Elapsed: `290.1s`
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
- Concepts/code/cautions: `491`
- Graph nodes: `727`
- Graph links: `1288`
- Questions: `5`

## Refine Loop

- Iteration `1`: `needs_refine` — Unit covers foundational Java concepts from syntax to OOP, but has severe duplication, missing page provenance for key concepts, and inconsistent granularity.
- Iteration `2`: `needs_refine` — Comprehensive coverage of Java fundamentals from syntax to OOP, but with critical duplication and missing page provenance for key concepts.

## NVIDIA Rate Audit

- `NVIDIA_API_KEY_1::qwen/qwen3-next-80b-a3b-instruct`: calls `4`, max 60s `2` / limit `20`, within `True`
- `NVIDIA_API_KEY_2::qwen/qwen3-next-80b-a3b-instruct`: calls `4`, max 60s `2` / limit `20`, within `True`
- `NVIDIA_API_KEY_3::qwen/qwen3-next-80b-a3b-instruct`: calls `4`, max 60s `2` / limit `20`, within `True`
- `NVIDIA_API_KEY_4::qwen/qwen3-next-80b-a3b-instruct`: calls `4`, max 60s `2` / limit `20`, within `True`
- `NVIDIA_API_KEY_5::qwen/qwen3-next-80b-a3b-instruct`: calls `4`, max 60s `2` / limit `20`, within `True`
- `NVIDIA_API_KEY_6::qwen/qwen3-next-80b-a3b-instruct`: calls `3`, max 60s `2` / limit `20`, within `True`
- `NVIDIA_API_KEY_7::qwen/qwen3-next-80b-a3b-instruct`: calls `3`, max 60s `2` / limit `20`, within `True`
- aggregate `qwen/qwen3-next-80b-a3b-instruct`: calls `26`, max 60s `11` / limit `140`, within `True`

## Sample Questions

- Unit 01: Java에서 문자열 비교 시 == 연산자와 equals() 메서드의 차이를 설명하고, ==을 사용했을 때 발생할 수 있는 실제 버그 사례를 하나 제시하세요. 이 차이가 JVM의 메모리 구조와 어떻게 연결되는지 설명하세요. (pages: [51, 52])
- Unit 01: 전위 증감 연산자(++a)와 후위 증감 연산자(a++)가 혼합된 식에서 실행 순서가 어떻게 달라지는지, 다음 코드의 출력 결과를 예측하고 그 이유를 설명하세요: int a = 5; int b = a++ + ++a; System.out.println(b); (pages: [79, 80])
- Unit 01: JVM이 Java의 WORA(Write Once, Run Anywhere)를 가능하게 하는 메커니즘을 설명하세요. 만약 JVM이 없고 Java 소스 코드를 직접 기계어로 컴파일했다면, 어떤 문제점이 발생했을까요? 플랫폼 독립성의 핵심은 무엇인가요? (pages: [4, 14, 15])
- Unit 01: 다음 두 코드 조각 중 어느 것이 더 안전한가요? 이유를 설명하세요. (A) if (str != null && str.equals("test")) (B) if (str.equals("test") && str != null) 그리고 단락 평가(Short-Circuit Evaluation)가 이 선택에 어떤 영향을 미치는지 설명하세요. (pages: [51, 92])
- Unit 01: public 클래스는 반드시 파일명과 동일해야 한다는 규칙이 존재합니다. 이 규칙이 없었다면 Java 컴파일러는 어떤 문제를 겪었을까요? 이 규칙이 프로젝트 구조와 빌드 도구(Maven/Gradle)에 어떤 영향을 미치는지 설명하세요. (pages: [185])

## Graphify Query Smoke Test

```text
NODE Unit 01 Java 시작하기 [src= loc= community=]
NODE Unit 04 Java 의 연산자 [src= loc= community=]
NODE p51 [src= loc= community=]
NODE p52 [src= loc= community=]
NODE p145 [src= loc= community=]
NODE p144 [src= loc= community=]
NODE p57 [src= loc= community=]
NODE p221 [src= loc= community=]
NODE p58 [src= loc= community=]
NODE p191 [src= loc= community=]
NODE p64 [src= loc= community=]
NODE p25 [src= loc= community=]
NODE p4 [src= loc= community=]
NODE p88 [src= loc= community=]
NODE p85 [src= loc= community=]
NODE JVM이 Java의 WORA(Write Once, Run Anywhere)를 가능하게 하는 메커니즘을 설명하세요. 만약 JVM이 없고 Java 소스 코드를 직접 기계어로 컴파일했다면, 어떤 문제점이 발생했을까요? 플 [src= loc= community=]
NODE p150 [src= loc= community=]
NODE p143 [src= loc= community=]
NODE p108 [src= loc= community=]
NODE p121 [src= loc= community=]
NODE p148 [src= loc= community=]
NODE p91 [src= loc= community=]
NODE p183 [src= loc= community=]
NODE p224 [src= loc= community=]
NODE p14 [src= loc= community=]
NODE p101 [src= loc= community=]
NODE p141 [src= loc= community=]
NODE p225 [src= loc= community=]
NODE p23 [src= loc= community=]
NODE p149 [src= loc= community=]
NODE p223 [src= loc= community=]
NODE p8 [src= loc= community=]
NODE p92 [src= loc= community=]
NODE p120 [src= loc= community=]
NODE p229 [src= loc= community=]
NODE p116 [src= loc= community=]
NODE p195 [src= loc= community=]
NODE p201 [src= loc= community=]
NODE p7 [src= loc= community=]
NODE p128 [src= loc= community=]
NODE p126 [src= loc= community=]
NODE p62 [src= loc= community=]
NODE p48 [src= loc= community=]
NODE p186 [src= loc= community=]
NODE p61 [src= loc= community=]
NODE p22 [src= loc= community=]
NODE p79 [src= loc= community=]
NODE p63 [src= loc= community=]
NODE p46 [src= loc= community=]
NODE p82 [src= loc= community=]
NODE p71 [src= loc= community=]
NODE p222 [src= loc= community=]
NODE String equality with equals() [src= loc= community=]
NODE p34 [src= loc= community=]
NODE p33 [src= loc= community=]
NODE p29 [src= loc= community=]
NODE p241 [src= loc= community=]
NODE p199 [src= loc= community=]
NODE p26 [src= loc= community=]
NODE p81 [src= loc= community=]
NODE p125 [src= loc= community=]
NODE p102 [src= loc= community=]
NODE p6 [src= loc= community=]
NODE p113 [src= loc= community=]
NODE p72 [src= loc= community=]
NODE p172 [src= loc= community=]
NODE p15 [src= loc= community=]
NODE p5 [src= loc= community=]
NODE p179 [src= loc= commu
... (truncated to ~800 token budget)
```
