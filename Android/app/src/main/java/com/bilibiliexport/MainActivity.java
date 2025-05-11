package com.bilibiliexport;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.provider.DocumentsContract;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.documentfile.provider.DocumentFile;

import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {

    private static final int REQUEST_CODE_CACHE_DIR = 1;
    private static final int REQUEST_CODE_EXPORT_DIR = 2;

    private ExecutorService executorService = Executors.newSingleThreadExecutor();
    private int totalFolders = 0;
    private int processedFolders = 0;

    private Uri cacheDirUri;   // 缓存目录URI
    private Uri exportDirUri;  // 导出目录URI
    private TextView tvStatus;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        Button btnSelectCache = findViewById(R.id.btn_select_cache);
        Button btnSelectExport = findViewById(R.id.btn_select_export);
        Button btnExport = findViewById(R.id.btn_export);
        tvStatus = findViewById(R.id.tv_status);

        // 选择缓存目录
        btnSelectCache.setOnClickListener(v -> openDirectoryPicker(REQUEST_CODE_CACHE_DIR));

        // 选择导出目录
        btnSelectExport.setOnClickListener(v -> openDirectoryPicker(REQUEST_CODE_EXPORT_DIR));

        // 执行导出操作
        btnExport.setOnClickListener(v -> {
            if (cacheDirUri == null || exportDirUri == null) {
                Toast.makeText(this, "请先选择两个目录！", Toast.LENGTH_SHORT).show();
                return;
            }
            exportFolderNames();
        });
    }

    // 打开目录选择器
    private void openDirectoryPicker(int requestCode) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        intent.putExtra(DocumentsContract.EXTRA_PROMPT, "请选择B站缓存目录");
        intent.addFlags(
                Intent.FLAG_GRANT_READ_URI_PERMISSION |
                        Intent.FLAG_GRANT_WRITE_URI_PERMISSION |
                        Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION |
                        Intent.FLAG_GRANT_PREFIX_URI_PERMISSION
        );

        // 尝试直接定位到Android/data目录（需要用户授权）
        Uri initialUri = DocumentsContract.buildDocumentUri(
                "com.android.externalstorage.documents",
                "primary:Android/data");
        intent.putExtra(DocumentsContract.EXTRA_INITIAL_URI, initialUri);

        startActivityForResult(intent, requestCode);
    }

    // 处理目录选择结果
    @Override
    protected void onActivityResult(int requestCode, int resultCode, @Nullable Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null) return;

        Uri uri = data.getData();
        switch (requestCode) {
            case REQUEST_CODE_CACHE_DIR:
                cacheDirUri = uri;
                savePersistentPermission(uri);
                tvStatus.setText("缓存目录已选择: " + getPathFromUri(uri));
                break;
            case REQUEST_CODE_EXPORT_DIR:
                exportDirUri = uri;
                savePersistentPermission(uri);
                tvStatus.setText("导出目录已选择: " + getPathFromUri(uri));
                break;
        }
    }

    // 保存持久化权限
    private void savePersistentPermission(Uri uri) {
        try {
            getContentResolver().takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            );
        } catch (SecurityException e) {
            Log.e("SAF", "权限保存失败: " + e.getMessage());
        }
    }

    // 获取目录路径（仅用于显示）
    private String getPathFromUri(Uri uri) {
        return uri.getPath().replace("tree/primary:", "/storage/emulated/0/");
    }

    // 导出文件夹名称到文本文件
    private void exportFolderNames() {
        runOnUiThread(() -> {
            Toast.makeText(MainActivity.this, "请耐心等待", Toast.LENGTH_SHORT).show();
        });

        executorService.execute(() -> {
            try {
                // 1. 遍历缓存目录下的所有文件夹（在后台线程执行）
                DocumentFile cacheDir = DocumentFile.fromTreeUri(this, cacheDirUri);
                List<String> folderNames = new ArrayList<>();

                if (cacheDir != null && cacheDir.exists()) {
                    totalFolders = 0;
                    // 先统计总数用于进度计算
                    for (DocumentFile file : cacheDir.listFiles()) {
                        if (file.isDirectory()) {
                            totalFolders++;
                        }
                    }

                    // 重置计数器
                    processedFolders = 0;

                    // 再次遍历获取名称
                    for (DocumentFile file : cacheDir.listFiles()) {
                        if (file.isDirectory()) {
                            folderNames.add(file.getName());
                            processedFolders++;

                            // 更新进度到主线程（每处理1个文件夹更新一次）
                            runOnUiThread(() -> tvStatus.setText(
                                    "导出进度: " + processedFolders + "/" + totalFolders
                            ));
                        }
                    }
                }

                // 2. 在导出目录中创建文本文件（在后台线程执行）
                String fileName = "folder_list.txt";
                DocumentFile exportDir = DocumentFile.fromTreeUri(this, exportDirUri);
                DocumentFile outputFile = exportDir.createFile("text/plain", fileName);

                // 3. 写入文件夹名称（在后台线程执行）
                if (outputFile != null) {
                    try (OutputStream os = getContentResolver().openOutputStream(outputFile.getUri())) {
                        for (String name : folderNames) {
                            os.write((name + "\n").getBytes());
                        }
                        // 写入完成后更新状态
                        runOnUiThread(() -> {
                            tvStatus.setText("导出完成！");
                            Toast.makeText(MainActivity.this, "导出成功: " + fileName, Toast.LENGTH_SHORT).show();
                        });
                    }
                }
            } catch (Exception e) {
                Log.e("Export", "导出失败", e);
                runOnUiThread(() -> {
                    tvStatus.setText("导出失败");
                    Toast.makeText(MainActivity.this, "导出失败: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                });
            }
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        executorService.shutdown();
    }
}