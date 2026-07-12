import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 한 번의 프로그램 실행 동안 이루어진 변환 기록들을 저장하고 관리하는 클래스.
 *
 * <p>내부 저장 구조로 ArrayList를 선택한 이유(대안 비교):
 * <ul>
 *   <li>이 클래스의 사용 패턴은 "끝에 추가(add)"와 "처음부터 끝까지 순회해서
 *       출력(report)" 두 가지뿐이고, 중간 삽입/삭제는 없다. ArrayList는
 *       끝에 추가하는 연산이 상각(amortized) O(1)이고, 배열 기반이라
 *       순차 접근 시 캐시 지역성이 좋아 이 사용 패턴에 잘 맞는다.</li>
 *   <li>대안으로 LinkedList를 생각해 볼 수 있는데, LinkedList는 중간
 *       삽입/삭제가 잦은 경우에 유리하다. 이 프로그램에는 그런 연산이
 *       전혀 없고, 오히려 노드마다 앞/뒤 참조를 추가로 저장해서 메모리
 *       오버헤드만 늘어난다. 따라서 이 시스템의 성능/메모리 제약에서는
 *       ArrayList가 더 합리적인 선택이다.</li>
 *   <li>기록 전체를 리스트로 들고 있는 대신 "누적 합계 + 개수" 같은
 *       집계값만 들고 있는 대안도 있었지만, ConversionReport가 "마지막
 *       변환 결과"와 "전체 이력 목록"까지 보여줘야 하므로 개별 레코드를
 *       모두 보존하는 현재 구조가 요구사항에 더 맞는다.</li>
 * </ul>
 *
 * <p>ConversionReport를 필드로 들고 이력 출력을 위임한다 — 이 클래스는
 * "저장/관리"에만 집중하고, "어떻게 보기 좋게 출력할지"는 ConversionReport의
 * 책임으로 분리했다(단일 책임 원칙).
 */
public class ConversionHistory {

    private final List<ConversionRecord> records;
    private final ConversionReport report;

    public ConversionHistory() {
        this.records = new ArrayList<>();
        this.report = new ConversionReport();
    }

    /**
     * 변환 기록 1건을 이력에 추가한다.
     *
     * @param record 추가할 변환 기록 (null 불가)
     */
    public void add(ConversionRecord record) {
        if (record == null) {
            throw new IllegalArgumentException("record는 null일 수 없습니다.");
        }
        records.add(record);
    }

    /**
     * 지금까지 저장된 변환 횟수를 반환한다.
     *
     * <p>반환 타입은 List.size()의 계약을 그대로 따르는 int다.
     * int의 상한(Integer.MAX_VALUE, 약 21억)은 이 프로그램처럼 사람이
     * 콘솔에서 한 번의 실행 동안 직접 입력하는 변환 횟수에 비하면
     * 사실상 무한대에 가까워서, 오버플로우를 실질적으로 걱정할 필요는
     * 없다.
     *
     * @return 현재까지의 변환 횟수
     */
    public int size() {
        return records.size();
    }

    /**
     * 저장된 변환 기록 목록을 반환한다. 외부에서 이력을 임의로 수정하지
     * 못하도록 읽기 전용(unmodifiable) 뷰로 감싸서 반환한다.
     *
     * @return 읽기 전용 변환 기록 목록
     */
    public List<ConversionRecord> getRecords() {
        return Collections.unmodifiableList(records);
    }

    /**
     * ConversionReport에 위임해서 이력 요약을 보기 좋게 출력한다.
     */
    public void printSummary() {
        report.print(records);
    }
}
