import java.util.ArrayList;
import java.util.List;

/**
 * 이번 실행에서 입력받은 학생 정보를 기록으로 저장/관리하는 클래스.
 */
public class InputHistory {
    private List<Student> history;

    public InputHistory() {
        this.history = new ArrayList<>();
    }

    public void addAll(List<Student> students) {
        history.addAll(students);
    }

    public void addRecord(Student student) {
        history.add(student);
    }

    public List<Student> getHistory() {
        return history;
    }

    public int getRecordCount() {
        return history.size();
    }

    public void printHistory() {
        System.out.println("\n===== 입력 기록 (" + history.size() + "건) =====");
        int index = 1;
        for (Student student : history) {
            System.out.println(index + ". " + student.getName() + " - " + student.getScore() + "점");
            index++;
        }
    }
}
