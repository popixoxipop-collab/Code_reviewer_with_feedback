import java.util.Scanner;

/**
 * 프로그램 진입점. Scanner로 사용자 입력을 받아 TemperatureConverter로
 * 변환하고, ConversionHistory에 기록한 뒤, 종료 시 이력 요약을 출력한다.
 *
 * <p>변환 "방향"을 별도의 메뉴(1: C-&gt;F, 2: F-&gt;C)로 받는 대신,
 * 사용자가 입력한 값의 "현재 단위"를 물어서 방향을 자동으로 결정하는
 * 방식을 택했다. 예를 들어 단위로 "C"를 입력하면 자동으로 섭씨-&gt;화씨
 * 변환이, "F"를 입력하면 화씨-&gt;섭씨 변환이 수행된다. 입력해야 할
 * 항목이 하나 줄고, 사용자가 "내가 가진 값이 무슨 단위인지"만 알면
 * 되므로 더 직관적이라고 판단했다.
 */
public class Main {

    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        TemperatureConverter converter = new TemperatureConverter();
        ConversionHistory history = new ConversionHistory();

        System.out.println("===== 섭씨/화씨 온도 변환기 =====");
        System.out.println("종료하려면 온도 값 입력 시 'quit'을 입력하세요.");

        while (true) {
            System.out.print("\n변환할 온도 값을 입력하세요 (quit 입력 시 종료): ");
            String valueInput = scanner.nextLine().trim();

            if (valueInput.equalsIgnoreCase("quit")) {
                break;
            }

            double value;
            try {
                value = Double.parseDouble(valueInput);
            } catch (NumberFormatException e) {
                System.out.println("숫자로 인식할 수 없는 값입니다: \"" + valueInput + "\". 다시 입력해 주세요.");
                continue;
            }

            System.out.print("위 값의 현재 단위를 입력하세요 (C 또는 F): ");
            String unitInput = scanner.nextLine().trim();

            try {
                ConversionRecord record = converter.convert(value, unitInput);
                history.add(record);
                System.out.println("변환 결과: " + record);
                System.out.println("(이번 실행에서 " + history.size() + "번째 변환입니다)");
            } catch (IllegalArgumentException e) {
                System.out.println("오류: " + e.getMessage());
            }
        }

        history.printSummary();
        scanner.close();
    }
}
