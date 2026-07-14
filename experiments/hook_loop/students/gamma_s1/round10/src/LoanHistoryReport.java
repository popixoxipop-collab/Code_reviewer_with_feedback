import java.util.List;

/**
 * 반납 이력을 출력하는 클래스.
 *
 * 매개변수 타입을 ArrayList가 아닌 List<BookLoan>으로 선언한 이유:
 * 이 클래스는 순회(for-each)만 하고, 인덱스 접근이나 리스트 내부 구현에
 * 의존하는 연산은 쓰지 않는다. 구체 타입(ArrayList) 대신 인터페이스
 * (List)로 받으면 Main이 내부적으로 어떤 List 구현을 쓰든 이 클래스는
 * 한 글자도 고칠 필요가 없다 - Main의 자료구조 선택에 이 클래스가
 * 결합되지 않도록 격리한 것이다.
 *
 * ArrayList vs LinkedList (Main이 실제로 선택한 구조에 대한 근거):
 * - ArrayList: 연속 메모리라 순차 순회 시 캐시 지역성이 좋고, 끝에
 *   추가(add)는 상수 시간 상각(amortized O(1))이다. 이 프로그램은
 *   반납 건을 끝에만 추가하고(returns.add(...)) 중간 삽입/삭제가
 *   전혀 없다.
 * - LinkedList: 중간 삽입/삭제가 O(1)이라는 장점이 있지만, 이 코드
 *   어디에도 리스트 중간에 넣거나 빼는 연산(add(index, ...),
 *   remove(index))이 없음을 실제로 확인했다 - 즉 LinkedList의 강점을
 *   쓸 데가 없어 노드당 앞/뒤 포인터 오버헤드만 남는 손해다.
 * - 데이터 규모: 이 과제는 콘솔에서 사람이 직접 입력하는 규모(수십 건
 *   이내)라 O(n) 순회 자체가 성능 제약이 되지 않는다. 수만 건 이상
 *   스케일이면 이야기가 다르겠지만 지금 범위에서는 ArrayList로 충분하다.
 *
 * null 방어: history 자체가 null이면(호출자가 리스트를 초기화하지 않고
 * 넘기는 실수) for-each에서 즉시 NPE가 나 프로그램 전체가 종료되므로,
 * 진입 시점에 먼저 걸러 "이력 없음"으로 안전하게 출력한다. 리스트 안의
 * 개별 원소가 null인 경우도 스킵해서, 원소 하나의 문제로 나머지 이력
 * 출력까지 막히지 않게 했다 - 부분 실패가 전체 실패로 번지지 않도록
 * 하는 설계 의도다.
 */
public class LoanHistoryReport {

    public void printHistory(List<BookLoan> history) {
        System.out.println("===== 반납 이력 =====");

        if (history == null || history.isEmpty()) {
            System.out.println("(이력 없음)");
            return;
        }

        int index = 1;
        for (BookLoan record : history) {
            if (record == null) {
                continue;
            }
            System.out.println(index + ". " + record.toString());
            index++;
        }
    }
}
