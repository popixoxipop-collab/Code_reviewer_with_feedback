# Java Curriculum NVIDIA Parallel Pipeline Run

- PDF: `/Users/xox/Downloads/AI_JAVA_교안.pdf`
- Model: `qwen/qwen3-next-80b-a3b-instruct`
- Chunk size: `10` pages
- Chunks processed: `26`
- Max workers: `4`
- Dry run: `False`
- Elapsed: `327.5s`
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
- Graph nodes: `709`
- Graph links: `1164`
- Questions: `5`

## Refine Loop

- Iteration `1`: `needs_refine` — Comprehensive coverage of Java fundamentals from syntax to OOP, but with significant duplication, ambiguous page provenance, and missing concept-page alignment for key topics.
- Iteration `2`: `needs_refine` — Comprehensive coverage of Java fundamentals from syntax to OOP, but with critical issues in concept duplication, missing page provenance for key topics, and inconsistent granularity.

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

- Unit 01: 다음 두 코드 조각의 출력 결과는 어떻게 다릅니까? 이유를 설명하세요. 

코드 A: 
int a = 5; 
System.out.println(a++); 
System.out.println(a); 

코드 B: 
int a = 5; 
System.out.println(++a); 
System.out.println(a); (pages: [79, 80])
- Unit 01: 다음 코드에서 '=='와 'equals()' 중 어떤 것을 사용해야 올바른 문자열 비교가 되며, 왜 다른 방식은 잘못된 결과를 낼 수 있나요? 

String s1 = new String("hello"); 
String s2 = new String("hello"); 
System.out.println(s1 == s2); 
System.out.println(s1.equals(s2)); (pages: [51, 52])
- Unit 01: 다음 switch 문에서 break 문을 제거하면 어떤 결과가 발생합니까? 왜 그런 현상이 발생하며, 이를 방지하기 위한 원칙은 무엇인가요? 

int day = 3; 
switch(day) { 
  case 1: System.out.println("Mon"); 
  case 2: System.out.println("Tue"); 
  case 3: System.out.println("Wed"); 
  case 4: System.out.println("Thu"); 
  default: System.out.println("Invalid"); 
} (pages: [105, 104])
- Unit 01: 다음 코드에서 메서드 오버로딩과 오버라이딩을 구분할 수 있나요? 각각의 정의와 차이를 설명하고, 이 코드에서 어떤 것이 오버로딩이고 어떤 것이 오버라이딩인지 판별하세요. 

// 부모 클래스 
class Animal { 
  void makeSound() { System.out.println("Animal sound"); } 
} 

// 자식 클래스 
class Dog extends Animal { 
  void makeSound() { System.out.println("Bark"); } 
  void makeSound(String type) { System.out.println("Bark: " + type); } 
} (pages: [143, 144, 195])
- Unit 01: 다음 코드에서 Scanner의 next()와 nextLine()을 혼용할 때 발생할 수 있는 문제를 설명하고, 이를 해결하기 위한 올바른 패턴을 제시하세요. 

Scanner sc = new Scanner(System.in); 
System.out.print("정수 입력: "); 
int num = sc.nextInt(); 
System.out.print("문자열 입력: "); 
String str = sc.nextLine(); 
System.out.println("입력된 문자열: '" + str + "'"); (pages: [69, 70])

## Graphify Query Smoke Test

```text
NODE Unit 01 Java 시작하기 [src= loc= community=]
NODE Unit 02 변수와자료형 [src= loc= community=]
NODE Unit 03 사용자로부터입력받기 [src= loc= community=]
NODE Unit 04 Java 의 연산자 [src= loc= community=]
NODE p51 [src= loc= community=]
NODE Unit 05 조건문 [src= loc= community=]
NODE p144 [src= loc= community=]
NODE p52 [src= loc= community=]
NODE p57 [src= loc= community=]
NODE p145 [src= loc= community=]
NODE p58 [src= loc= community=]
NODE Unit 08 메소드 [src= loc= community=]
NODE AI_JAVA_교안.pdf [src= loc= community=]
NODE Unit 07 배열 [src= loc= community=]
NODE Unit 06 반복문 [src= loc= community=]
NODE p143 [src= loc= community=]
NODE p101 [src= loc= community=]
NODE p64 [src= loc= community=]
NODE p141 [src= loc= community=]
NODE p149 [src= loc= community=]
NODE p225 [src= loc= community=]
NODE p150 [src= loc= community=]
NODE p25 [src= loc= community=]
NODE p148 [src= loc= community=]
NODE p104 [src= loc= community=]
NODE p34 [src= loc= community=]
NODE p179 [src= loc= community=]
NODE p191 [src= loc= community=]
NODE p13 [src= loc= community=]
NODE p116 [src= loc= community=]
NODE p91 [src= loc= community=]
NODE p120 [src= loc= community=]
NODE p221 [src= loc= community=]
NODE p4 [src= loc= community=]
NODE p121 [src= loc= community=]
NODE p8 [src= loc= community=]
NODE NumberFormatException [src= loc= community=]
NODE p201 [src= loc= community=]
NODE 전위 vs 후위 증감 연산자 [src= loc= community=]
NODE p140 [src= loc= community=]
NODE 도트 연산자 [src= loc= community=]
NODE p125 [src= loc= community=]
NODE p85 [src= loc= community=]
NODE p241 [src= loc= community=]
NODE p181 [src= loc= community=]
NODE 도트 연산자 [src= loc= community=]
NODE p62 [src= loc= community=]
NODE 메서드 오버로딩 [src= loc= community=]
NODE p223 [src= loc= community=]
NODE p199 [src= loc= community=]
NODE p186 [src= loc= community=]
NODE p72 [src= loc= community=]
NODE p23 [src= loc= community=]
NODE p81 [src= loc= community=]
NODE p86 [src= loc= community=]
NODE p90 [src= loc= community=]
NODE p84 [src= loc= community=]
NODE p229 [src= loc= community=]
NODE p172 [src= loc= community=]
NODE p82 [src= loc= community=]
NODE ArrayIndexOutOfBoundsException [src= loc= community=]
NODE p97 [src= loc= community=]
NODE NumberFormatException [src= loc= community=]
NODE p63 [src= loc= community=]
NODE next() vs nextLine() [src= loc= community=]
NODE ArrayIndexOutOfBoundsException [src= loc= community=]
NODE p71 [src= loc= community=]
NODE 
... (truncated to ~800 token budget)
```
