# Java Curriculum NVIDIA Parallel Pipeline Run

- PDF: `/Users/xox/Downloads/AI_JAVA_교안.pdf`
- Model: `qwen/qwen3-next-80b-a3b-instruct`
- Chunk size: `10` pages
- Chunks processed: `3`
- Max workers: `2`
- Dry run: `False`
- Elapsed: `159.7s`
- NVIDIA key slots used: `{'NVIDIA_API_KEY_1': 1, 'NVIDIA_API_KEY_2': 1, 'NVIDIA_API_KEY_3': 1, 'NVIDIA_API_KEY_4': 1, 'NVIDIA_API_KEY_5': 1, 'NVIDIA_API_KEY_6': 1, 'NVIDIA_API_KEY_7': 0}`

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
- `graphify-out/graph.json`
- `graphify-out/GRAPH_REPORT.md`

## Counts

- Units: `2`
- Concepts/code/cautions: `50`
- Graph nodes: `86`
- Graph links: `139`
- Questions: `4`

## Refine Loop

- Iteration `1`: `needs_refine` — Unit 01 covers foundational Java concepts well, but Unit 02 duplicates content from Unit 01 without adding new concepts or page provenance for core topics like variables and data types.

## Sample Questions

- Unit 01: Java의 WORA(Write Once, Run Anywhere) 원칙이 실제로 작동하려면 JVM과 JDK가 각각 어떤 역할을 해야 하는가? 만약 사용자가 JDK를 설치하지 않고 JRE만 설치했다면, Java 프로그램을 개발할 수 있는가? 왜 그런가? (pages: [4, 13])
- Unit 01: main 메소드의 선언이 public static void main(String[] args)여야만 하는 이유는 무엇인가? 만약 public을 빼면 JVM은 어떻게 반응할까? 이는 Java의 실행 메커니즘과 어떤 관계가 있는가? (pages: [23, 22])
- Unit 01: System.out.println("Hello\nWorld")과 System.out.print("Hello\nWorld")의 출력 결과는 어떻게 다른가? 이스케이프 문자 \n의 역할이 println의 기능과 어떻게 중복되거나 보완되는가? 이 차이를 이해하지 못하면 어떤 실수를 범할 수 있는가? (pages: [24, 25, 27])
- Unit 01: Java가 C++보다 메모리 관리가 안전하다고 하지만, JVM이 메모리를 자동으로 관리한다고 해서 메모리 누수(Memory Leak)가 발생할 수 없는가? 예를 들어, static Collection에 무한히 객체를 추가하면 어떤 문제가 발생할 수 있는가? 이는 Java의 '안전성'이 무엇을 의미하는지에 대한 오해를 드러내는가? (pages: [7, 13])

## Graphify Query Smoke Test

```text
NODE Unit 01 Java 시작하기 [src= loc= community=]
NODE p25 [src= loc= community=]
NODE p4 [src= loc= community=]
NODE p23 [src= loc= community=]
NODE p13 [src= loc= community=]
NODE Java의 WORA(Write Once, Run Anywhere) 원칙이 실제로 작동하려면 JVM과 JDK가 각각 어떤 역할을 해야 하는가? 만약 사용자가 JDK를 설치하지 않고 JRE만 설치했다면, Java 프로그 [src= loc= community=]
NODE p8 [src= loc= community=]
NODE p24 [src= loc= community=]
NODE main 메소드의 선언이 public static void main(String[] args)여야만 하는 이유는 무엇인가? 만약 public을 빼면 JVM은 어떻게 반응할까? 이는 Java의 실행 메커니즘과 어떤 관 [src= loc= community=]
NODE p22 [src= loc= community=]
NODE p7 [src= loc= community=]
NODE p26 [src= loc= community=]
NODE Java가 C++보다 메모리 관리가 안전하다고 하지만, JVM이 메모리를 자동으로 관리한다고 해서 메모리 누수(Memory Leak)가 발생할 수 없는가? 예를 들어, static Collection에 무한히 객체를 [src= loc= community=]
NODE JDK [src= loc= community=]
NODE IntelliJ 프로젝트 생성 [src= loc= community=]
NODE p27 [src= loc= community=]
NODE Java 컴파일 및 실행 과정 [src= loc= community=]
NODE WORA(Write Once, Run Anywhere) [src= loc= community=]
NODE Java vs C/C++ [src= loc= community=]
NODE 자기소개 실습 과제 [src= loc= community=]
NODE Main 클래스 [src= loc= community=]
NODE JRE [src= loc= community=]
NODE 이스케이프 문자 \n [src= loc= community=]
NODE JVM [src= loc= community=]
NODE p29 [src= loc= community=]
NODE JVM 역할 [src= loc= community=]
NODE System.out.println() [src= loc= community=]
NODE main 메소드 [src= loc= community=]
NODE Java vs JavaScript [src= loc= community=]
NODE Java 취업 수요 [src= loc= community=]
NODE 객체지향 프로그래밍 [src= loc= community=]
NODE p5 [src= loc= community=]
NODE Java 활용 분야 - Android [src= loc= community=]
NODE Java 활용 분야 - 빅데이터 [src= loc= community=]
NODE IDE의 역할 [src= loc= community=]
NODE Java 생태계 [src= loc= community=]
NODE Java 장기 커리어 전망 [src= loc= community=]
NODE Java 활용 분야 - 웹 서비스 [src= loc= community=]
NODE p28 [src= loc= community=]
NODE Concept 'Java 정의' and 'JVM 역할' have overlapping evidence; both cite JVM for platform independence without distinguishing definition from function. [src= loc= community=]
NODE 패턴 출력 도전 과제 [src= loc= community=]
NODE 클래스와 객체 구분 [src= loc= community=]
NODE 변수와 자료형 단원 시작 [src= loc= community=]
NODE 이스케이프 문자 \t [src= loc= community=]
NODE Java 활용 분야 - 엔터프라이즈 [src= loc= community=]
NODE 이스케이프 문자 \\ [src= loc= community=]
NODE Java/Spring 점유율 [src= loc= community=]
NODE Java vs Python [src= loc= community=]
NODE Java 정의 [src= loc= community=]
NODE 한 줄 주석 [src= loc= community=]
NODE 여
... (truncated to ~800 token budget)
```
