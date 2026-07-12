import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

/**
 * Scanner로 학생 이름과 점수를 입력받는 클래스.
 */
public class GradeInputHandler {
    private Scanner scanner;

    public GradeInputHandler(Scanner scanner) {
        this.scanner = scanner;
    }

    /**
     * 지정된 인원 수만큼 학생 이름/점수를 입력받아 리스트로 반환한다.
     */
    public List<Student> inputStudents(int count) {
        List<Student> students = new ArrayList<>();

        for (int i = 1; i <= count; i++) {
            System.out.println("\n[" + i + "번째 학생 입력]");

            System.out.print("이름: ");
            String name = scanner.nextLine().trim();

            int score = readScore();

            students.add(new Student(name, score));
        }

        return students;
    }

    /**
     * 0~100 범위의 정수 점수를 입력받을 때까지 반복한다.
     */
    private int readScore() {
        int score = -1;
        boolean valid = false;

        while (!valid) {
            System.out.print("점수 (0~100): ");
            String input = scanner.nextLine().trim();

            try {
                score = Integer.parseInt(input);
                if (score >= 0 && score <= 100) {
                    valid = true;
                } else {
                    System.out.println("0에서 100 사이의 점수를 입력해주세요.");
                }
            } catch (NumberFormatException e) {
                System.out.println("숫자만 입력해주세요.");
            }
        }

        return score;
    }
}
