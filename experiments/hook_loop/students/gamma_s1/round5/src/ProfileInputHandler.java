import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

/**
 * 여러 학생의 정보를 입력받아 StudentProfile 목록을 만드는 클래스.
 *
 * [ArrayList 선택 근거]
 * - 이 클래스가 리스트에 대해 하는 쓰기 연산은 collectProfiles()에서 매 반복마다
 *   끝에 add()하는 것뿐이며, 코드 전체에서 중간 삽입/삭제 연산은 없다.
 *   즉 LinkedList가 유리한 "중간 삽입/삭제 O(1)" 특성을 전혀 활용하지 않는다.
 * - 이후 이 리스트를 소비하는 HeightAnalyzer / ProfileReport / HeightSummary는
 *   모두 순차 순회(for-each)만 하므로 ArrayList의 낮은 메모리 오버헤드와
 *   빠른 임의 접근이 더 유리하다.
 * - 반례: 나중에 "특정 학생 삭제" 나 "명단 중간에 전학생 삽입" 기능이 생기면
 *   이 근거는 더 이상 성립하지 않는다. 그런 요구가 생기면 삽입/삭제 빈도와
 *   위치를 다시 따져 LinkedList 등 다른 자료구조를 재검토해야 한다.
 *
 * [Scanner 자원 관리]
 * Scanner를 이 클래스 안에서 새로 만들지 않고 생성자로 주입받는다.
 * 클래스마다 new Scanner(System.in)을 만들면 System.in을 감싸는 스트림이
 * 여러 개 생기고, 그중 하나라도 close()하면 System.in 자체가 닫혀
 * 다른 Scanner까지 더는 입력을 못 받는 문제가 생길 수 있다.
 * 그래서 Main에서 만든 단일 Scanner를 여기로 전달받아 재사용하고,
 * close()는 프로그램이 끝나는 Main에서만 한 번 수행한다.
 */
public class ProfileInputHandler {

    private final Scanner scanner;

    public ProfileInputHandler(Scanner scanner) {
        this.scanner = scanner;
    }

    public List<StudentProfile> collectProfiles() {
        List<StudentProfile> profiles = new ArrayList<>();

        int count = readCount();
        for (int i = 1; i <= count; i++) {
            System.out.println("--- " + i + "번째 학생 정보 입력 ---");
            String name = readName();
            double height = readHeight();
            int age = readAge();
            boolean activeMember = readActiveMember();
            profiles.add(new StudentProfile(name, height, age, activeMember));
        }
        return profiles;
    }

    private int readCount() {
        while (true) {
            System.out.print("등록할 학생 수를 입력하세요: ");
            String input = scanner.nextLine().trim();
            try {
                int count = Integer.parseInt(input);
                if (count > 0) {
                    return count;
                }
                System.out.println("1명 이상의 숫자를 입력해주세요.");
            } catch (NumberFormatException e) {
                System.out.println("숫자로 입력해주세요.");
            }
        }
    }

    private String readName() {
        while (true) {
            System.out.print("이름: ");
            String name = scanner.nextLine().trim();
            if (!name.isEmpty()) {
                return name;
            }
            System.out.println("이름은 비어 있을 수 없습니다.");
        }
    }

    private double readHeight() {
        while (true) {
            System.out.print("키(cm): ");
            String input = scanner.nextLine().trim();
            try {
                double height = Double.parseDouble(input);
                if (height > 0) {
                    return height;
                }
                System.out.println("키는 0보다 큰 값이어야 합니다.");
            } catch (NumberFormatException e) {
                System.out.println("숫자로 입력해주세요. (예: 172.5)");
            }
        }
    }

    private int readAge() {
        while (true) {
            System.out.print("나이: ");
            String input = scanner.nextLine().trim();
            try {
                int age = Integer.parseInt(input);
                if (age > 0) {
                    return age;
                }
                System.out.println("나이는 0보다 큰 값이어야 합니다.");
            } catch (NumberFormatException e) {
                System.out.println("숫자로 입력해주세요.");
            }
        }
    }

    private boolean readActiveMember() {
        while (true) {
            System.out.print("활동 회원 여부 (Y/N): ");
            String input = scanner.nextLine().trim();
            // null-safe 비교: input.equalsIgnoreCase("Y") 대신
            // "Y".equalsIgnoreCase(input) 형태로 호출한다. 이렇게 하면 input이
            // 예상치 못하게 null이 되는 경우에도 NullPointerException 없이
            // 그냥 false로 처리되어 "다시 입력해주세요" 분기로 자연스럽게 빠진다.
            // (Scanner.nextLine()은 정상 흐름에서 null을 반환하지 않지만,
            // 변수가 아니라 리터럴에 equals를 호출하는 습관 자체를 지켜둔다.)
            if ("Y".equalsIgnoreCase(input)) {
                return true;
            } else if ("N".equalsIgnoreCase(input)) {
                return false;
            }
            System.out.println("Y 또는 N으로 입력해주세요.");
        }
    }
}
