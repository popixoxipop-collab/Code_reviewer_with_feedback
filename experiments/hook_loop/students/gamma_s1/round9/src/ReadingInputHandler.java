import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

/**
 * Scanner로 여러 건의 측정값을 입력받아 SensorReading 목록을 만드는 클래스.
 */
public class ReadingInputHandler {

    private Scanner scanner = new Scanner(System.in);

    /**
     * 자료구조 선택: ArrayList vs LinkedList
     * - 이 메서드는 리스트 끝에 계속 추가(add)만 하고, 이후 ReadingLog / AnomalyReport는
     *   둘 다 for-each로 순차 순회만 한다. 인덱스로 중간에 삽입하거나 특정 위치를
     *   제거하는 연산은 이 프로그램 어디에도 없다(실제 메서드 호출 패턴 기준).
     * - 그래서 LinkedList의 장점(중간 삽입/삭제가 O(1))을 실제로 활용할 여지가 없고,
     *   ArrayList가 순차 접근·메모리 지역성 면에서 더 유리하다고 판단해 ArrayList를 선택.
     * - 만약 나중에 "특정 센서 ID의 측정값만 앞으로 재정렬" 같은 요구가 추가돼서
     *   중간 삽입/삭제가 실제로 필요해지면 그때 다시 LinkedList를 검토하면 되고,
     *   지금 코드 상태에서 미리 LinkedList를 쓰는 것은 근거 없는 선반영이라고 봄.
     */
    public List<SensorReading> collectReadings() {
        List<SensorReading> readings = new ArrayList<>();

        System.out.print("측정할 데이터 개수를 입력하세요: ");
        // TODO: count 파싱 자체에는 예외처리를 안 해놨음(숫자가 아닌 값을 넣으면
        // NumberFormatException으로 프로그램이 바로 종료됨). 지금은 정상 입력만
        // 가정하고 넘어감 - 클래스 통합 다듬는 단계에서 보강할 예정.
        int count = Integer.parseInt(scanner.nextLine().trim());

        int saved = 0;
        for (int i = 0; i < count; i++) {
            System.out.println("=== " + (i + 1) + "번째 측정값 입력 ===");

            System.out.print("센서 ID: ");
            String sensorId = scanner.nextLine().trim();

            System.out.print("온도(C): ");
            String tempInput = scanner.nextLine().trim();

            System.out.print("습도(%, 정수): ");
            String humidityInput = scanner.nextLine().trim();

            // 형변환 + 범위 검증은 ReadingValidator에 위임한다.
            // 이 클래스가 직접 Integer.parseInt/Double.parseDouble을 try-catch로
            // 감싸지 않는 이유: 검증 규칙이 바뀌었을 때 ReadingValidator만 고치면 되고,
            // 여러 입력 경로(지금은 Scanner뿐이지만)가 같은 규칙을 공유할 수 있게 하려는 것.
            if (!ReadingValidator.isValidTemperature(tempInput)) {
                System.out.println(">> 온도 값이 올바르지 않아 이 측정값은 저장하지 않습니다.");
                continue;
            }
            if (!ReadingValidator.isValidHumidity(humidityInput)) {
                System.out.println(">> 습도 값이 올바르지 않아(0~100 범위 아님 또는 정수 아님) 이 측정값은 저장하지 않습니다.");
                continue;
            }

            double temperature = Double.parseDouble(tempInput);
            int humidity = Integer.parseInt(humidityInput);

            readings.add(new SensorReading(sensorId, temperature, humidity));
            saved++;
        }

        // 유효하지 않은 입력은 그냥 건너뛰기 때문에 최종적으로 saved <= count 이다.
        // "실패한 만큼 다시 입력받기"까지는 시간 관계상 구현하지 않음(통합 단계 TODO).
        System.out.println(count + "건 중 " + saved + "건 저장 완료.\n");

        return readings;
    }
}
